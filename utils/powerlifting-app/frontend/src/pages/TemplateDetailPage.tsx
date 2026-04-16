import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Container, LoadingOverlay } from '@mantine/core'
import { fetchTemplate } from '../api/client'
import { TemplateDetail } from '../components/templates/TemplateDetail'
import type { Template } from '@powerlifting/types'

export default function TemplateDetailPage() {
  const { sk } = useParams<{ sk: string }>()
  const [template, setTemplate] = useState<Template | null>(null)
  const [loading, setLoading] = useState(true)

  const loadTemplate = () => {
    if (sk) {
      setLoading(true)
      fetchTemplate(sk)
        .then(setTemplate)
        .finally(() => setLoading(false))
    }
  }

  useEffect(() => {
    loadTemplate()
  }, [sk])

  if (!template && !loading) return <div>Template not found</div>

  return (
    <Container size="lg" py="xl">
      <LoadingOverlay visible={loading} />
      {template && (
        <TemplateDetail template={template} onRefresh={loadTemplate} />
      )}
    </Container>
  )
}
