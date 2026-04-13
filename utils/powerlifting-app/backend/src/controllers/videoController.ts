import { v4 as uuidv4 } from 'uuid'
import { GetCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { S3Client, DeleteObjectCommand } from '@aws-sdk/client-s3'
import { Upload } from '@aws-sdk/lib-storage'
import { docClient, TABLE } from '../db/dynamo'
import { AppError } from '../middleware/errorHandler'
import { transformProgram } from '../db/transforms'
import type { Session, SessionVideo, VideoLibraryItem } from '@powerlifting/types'

const PK = 'operator'

const S3_BUCKET = process.env.VIDEOS_BUCKET || 'powerlifting-session-videos'
const S3_REGION = process.env.AWS_REGION || 'ca-central-1'

const s3Client = new S3Client({
  region: S3_REGION,
  credentials: process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY
    ? {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      }
    : undefined,
})

function stripUndefined(obj: any): any {
  if (obj === null || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(stripUndefined)
  const cleaned: any = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined) cleaned[k] = stripUndefined(v)
  }
  return cleaned
}

/**
 * Resolve a version string to the actual SK.
 */
async function resolveVersionSk(version: string): Promise<string> {
  if (version === 'current') {
    const pointerCommand = new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: 'program#current' },
    })
    const pointerResult = await docClient.send(pointerCommand)
    if (!pointerResult.Item) return 'program#v001'
    return (pointerResult.Item as any).ref_sk || 'program#v001'
  }
  return `program#${version}`
}

/**
 * Upload a video to S3 and add metadata to session
 */
export async function uploadSessionVideo(
  version: string,
  sessionDate: string,
  file: Buffer,
  filename: string,
  mimeType: string,
  exerciseName?: string,
  setNumber?: number,
  notes?: string
): Promise<SessionVideo> {
  const sk = await resolveVersionSk(version)

  // Generate video ID
  const videoId = uuidv4()
  const s3Key = `videos/${sessionDate}/${videoId}.mp4`

  // Upload to S3 with metadata for Lambda
  const upload = new Upload({
    client: s3Client,
    params: {
      Bucket: S3_BUCKET,
      Key: s3Key,
      Body: file,
      ContentType: mimeType,
      Metadata: {
        video_id: videoId,
        session_date: sessionDate,
        pk: PK,
        sk,
      },
    },
  })

  await upload.done()

  const videoUrl = `https://${S3_BUCKET}.s3.${S3_REGION}.amazonaws.com/${s3Key}`

  const video: SessionVideo = {
    video_id: videoId,
    s3_key: s3Key,
    video_url: videoUrl,
    ...(exerciseName !== undefined && { exercise_name: exerciseName }),
    ...(setNumber !== undefined && { set_number: setNumber }),
    ...(notes !== undefined && { notes }),
    uploaded_at: new Date().toISOString(),
    thumbnail_status: 'pending',
  }

  // Add to session in DynamoDB
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  const sessionIndex = sessions.findIndex(s => s.date === sessionDate)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${sessionDate} not found`, 404)
  }

  // Initialize videos array if it doesn't exist
  if (!sessions[sessionIndex].videos) {
    sessions[sessionIndex].videos = []
  }

  sessions[sessionIndex].videos!.push(video)

  // Safely update both sessions and metadata
  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': stripUndefined(sessions),
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)

  return video
}

/**
 * Remove a video from a session
 */
export async function removeSessionVideo(
  version: string,
  sessionDate: string,
  videoId: string
): Promise<void> {
  const sk = await resolveVersionSk(version)

  // Get session to find video info
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  const sessionIndex = sessions.findIndex(s => s.date === sessionDate)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${sessionDate} not found`, 404)
  }

  if (!sessions[sessionIndex].videos) {
    throw new AppError(`Session has no videos`, 404)
  }

  const video = sessions[sessionIndex].videos!.find(v => v.video_id === videoId)

  if (!video) {
    throw new AppError(`Video ${videoId} not found`, 404)
  }

  // Delete from S3
  const deletePromises: Promise<unknown>[] = [
    s3Client.send(new DeleteObjectCommand({ Bucket: S3_BUCKET, Key: video.s3_key })),
  ]

  if (video.thumbnail_s3_key) {
    deletePromises.push(
      s3Client.send(new DeleteObjectCommand({ Bucket: S3_BUCKET, Key: video.thumbnail_s3_key }))
    )
  }

  await Promise.all(deletePromises)

  // Remove from session
  sessions[sessionIndex].videos = sessions[sessionIndex].videos!.filter(v => v.video_id !== videoId)

  // Remove videos array if empty
  if (sessions[sessionIndex].videos!.length === 0) {
    delete sessions[sessionIndex].videos
  }

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': stripUndefined(sessions),
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}

/**
 * Update video thumbnail URL (called by Lambda)
 */
export async function updateVideoThumbnail(
  version: string,
  sessionDate: string,
  videoId: string,
  thumbnailUrl: string,
  thumbnailS3Key: string,
  status: 'ready' | 'failed'
): Promise<void> {
  const sk = await resolveVersionSk(version)

  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  const sessionIndex = sessions.findIndex(s => s.date === sessionDate)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${sessionDate} not found`, 404)
  }

  if (!sessions[sessionIndex].videos) {
    throw new AppError(`Session has no videos`, 404)
  }

  const videoIndex = sessions[sessionIndex].videos!.findIndex(
    v => v.video_id === videoId
  )

  if (videoIndex === -1) {
    throw new AppError(`Video ${videoId} not found`, 404)
  }

  sessions[sessionIndex].videos![videoIndex] = {
    ...sessions[sessionIndex].videos![videoIndex],
    thumbnail_url: thumbnailUrl,
    thumbnail_s3_key: thumbnailS3Key,
    thumbnail_status: status,
  }

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': stripUndefined(sessions),
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}

export async function getVideoLibrary(
  version: string,
  exercise?: string,
  sort: 'newest' | 'oldest' = 'newest'
): Promise<{ videos: VideoLibraryItem[]; exercises: string[] }> {
  const sk = await resolveVersionSk(version)

  const command = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
  })

  const result = await docClient.send(command)
  if (!result.Item) {
    return { videos: [], exercises: [] }
  }

  // Transform program to get derived week_number and phase_name
  const program = transformProgram(result.Item)
  const sessions = program.sessions
  const items: VideoLibraryItem[] = []
  const exerciseSet = new Set<string>()

  for (const session of sessions) {
    if (!session.videos || session.videos.length === 0) continue

    for (const video of session.videos) {
      if (exercise && video.exercise_name !== exercise) continue

      const match = video.exercise_name
        ? session.exercises.find((e) => e.name === video.exercise_name)
        : undefined

      if (video.exercise_name) exerciseSet.add(video.exercise_name)

      items.push({
        video,
        session_date: session.date,
        day: session.day,
        week_number: session.week_number,
        phase_name: session.phase?.name ?? '',
        exercise_sets: match?.sets ?? 0,
        exercise_reps: match?.reps ?? 0,
        exercise_kg: match?.kg ?? null,
      })
    }
  }

  items.sort((a, b) => {
    const cmp = a.session_date.localeCompare(b.session_date)
    return sort === 'newest' ? -cmp : cmp
  })

  return {
    videos: stripUndefined(items),
    exercises: Array.from(exerciseSet).sort(),
  }
}

