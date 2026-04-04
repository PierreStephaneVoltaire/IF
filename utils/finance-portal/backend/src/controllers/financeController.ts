import { Request, Response, NextFunction } from 'express';
import {
  resolvePointer,
  saveVersioned,
  listVersions,
  getVersion,
  initializeSnapshot,
} from '../db/dynamodb.js';
import { FinanceSnapshot, VersionListItem } from '@finance-portal/types';
import { createError } from '../middleware/errorHandler.js';

const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator';

interface FinanceResponse {
  snapshot: FinanceSnapshot;
  version: {
    sk: string;
    label: string;
    updated_at: string;
  };
}

/**
 * GET /api/finance/current
 * Get the current finance snapshot
 */
export async function getCurrentSnapshot(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const resolved = await resolvePointer(pk);

    if (!resolved) {
      // Initialize if no snapshot exists
      const snapshot = await initializeSnapshot(pk);
      const response: FinanceResponse = {
        snapshot,
        version: {
          sk: snapshot.sk,
          label: snapshot.version_label,
          updated_at: snapshot.updated_at,
        },
      };
      res.json(response);
      return;
    }

    const response: FinanceResponse = {
      snapshot: resolved.item,
      version: {
        sk: resolved.versionedSk,
        label: resolved.item.version_label,
        updated_at: resolved.item.updated_at,
      },
    };
    res.json(response);
  } catch (error) {
    next(error);
  }
}

/**
 * PUT /api/finance
 * Save a full snapshot (creates new version)
 */
export async function saveSnapshot(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const snapshot = req.body as FinanceSnapshot;

    if (!snapshot) {
      throw createError('Snapshot body is required', 400, 'VALIDATION_ERROR');
    }

    const changeLogEntry = req.body._changeLogEntry as string | undefined;
    const newSk = await saveVersioned(pk, snapshot, changeLogEntry);

    // Return updated snapshot
    const resolved = await resolvePointer(pk);
    const response: FinanceResponse = {
      snapshot: resolved!.item,
      version: {
        sk: newSk,
        label: resolved!.item.version_label,
        updated_at: resolved!.item.updated_at,
      },
    };

    res.json(response);
  } catch (error) {
    next(error);
  }
}

/**
 * GET /api/finance/versions
 * List all versions
 */
export async function listAllVersions(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const versions = await listVersions(pk);
    res.json({ versions });
  } catch (error) {
    next(error);
  }
}

/**
 * GET /api/finance/versions/:sk
 * Get a specific version
 */
export async function getSpecificVersion(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { sk } = req.params;

    if (!sk) {
      throw createError('Version sk is required', 400, 'VALIDATION_ERROR');
    }

    const snapshot = await getVersion(pk, sk);

    if (!snapshot) {
      throw createError('Version not found', 404, 'NOT_FOUND');
    }

    const response: FinanceResponse = {
      snapshot,
      version: {
        sk: snapshot.sk,
        label: snapshot.version_label,
        updated_at: snapshot.updated_at,
      },
    };
    res.json(response);
  } catch (error) {
    next(error);
  }
}
