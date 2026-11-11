'use client'

import { useState, useRef, useEffect, useCallback, DragEvent, ChangeEvent } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { apiRequest, errorMessage } from '@/lib/api'
import { JOB_ERROR_COPY, JOB_STATUS_COPY } from '@/lib/explain'
import type { Job } from '@/lib/types'

const POLL_INTERVAL_MS = 1000
const POLL_TIMEOUT_MS = 5 * 60 * 1000

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<Job['status']>('queued')
  const [error, setError] = useState('')
  const [elapsedMs, setElapsedMs] = useState(0)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const cancelledRef = useRef(false)
  const router = useRouter()

  // Release the preview object URL and stop polling when the page goes away
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  useEffect(() => {
    cancelledRef.current = false
    return () => {
      cancelledRef.current = true
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const selectFile = (selectedFile: File) => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
    }
    setFile(selectedFile)
    setError('')
    if (selectedFile.type.startsWith('image/')) {
      setPreviewUrl(URL.createObjectURL(selectedFile))
    }
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) selectFile(e.target.files[0])
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0])
  }

  const handleClearFile = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
    }
    setFile(null)
    setError('')
  }

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a media file to verify.')
      return
    }

    setLoading(true)
    setError('')
    setStatus('queued')
    setElapsedMs(0)

    const startTime = Date.now()
    timerRef.current = setInterval(() => setElapsedMs(Date.now() - startTime), 100)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const created = await apiRequest<Job>('/api/v1/jobs/', { method: 'POST', body: formData })

      // Poll the job until it finishes. The server answers at once, so the page stays responsive.
      let job = created
      while (job.status === 'queued' || job.status === 'running') {
        if (cancelledRef.current) return
        if (Date.now() - startTime > POLL_TIMEOUT_MS) {
          throw new Error('The analysis is taking too long. Check the dashboard later.')
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
        job = await apiRequest<Job>(`/api/v1/jobs/${created.job_id}`)
        setStatus(job.status)
      }

      if (job.status === 'failed' || !job.report_id) {
        throw new Error(JOB_ERROR_COPY[job.error ?? ''] ?? JOB_STATUS_COPY.failed)
      }
      setStatus('done')
      router.push(`/report/${job.report_id}`)
    } catch (err: unknown) {
      if (!cancelledRef.current) {
        setError(errorMessage(err))
        setLoading(false)
      }
    } finally {
      stopTimer()
    }
  }

  const formatElapsed = (ms: number): string => `${(ms / 1000).toFixed(1)}s`

  return (
    <main id="main-content" className="page page-upload">
      <section className="upload-intro">
        <p className="eyebrow">Media verification</p>
        <h1 className="page-title">Run Verification</h1>
        <p className="upload-description">
          Upload an image, audio, or video file. Several independent checks score it, and the result is written to a
          tamper-evident record. When the checks cannot decide, the report says so and asks for a person to review.
        </p>
      </section>

      <section className="upload-shell card-soft">
        {!loading ? (
          <>
            <div
              className={`upload-dropzone ${isDragging ? 'upload-dropzone-active' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-upload')?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  document.getElementById('file-upload')?.click()
                }
              }}
              aria-label="Choose a media file, or drop one here"
            >
              <div className="upload-guidance">
                <h2>{isDragging ? 'Drop the file now' : 'Select or drop a media file'}</h2>
                <p>Supported formats: JPEG, PNG, WEBP, MP4, MP3. Maximum size: 50 MB.</p>
              </div>

              <input
                type="file"
                id="file-upload"
                className="sr-only-input"
                onChange={handleFileChange}
                accept="image/jpeg,image/png,image/webp,video/mp4,audio/mpeg"
              />

              {!file && (
                <button
                  type="button"
                  className="btn btn-secondary upload-file-trigger"
                  onClick={(e) => {
                    e.stopPropagation()
                    document.getElementById('file-upload')?.click()
                  }}
                >
                  Choose local file
                </button>
              )}

              {file && (
                <div className="upload-preview-container" onClick={(e) => e.stopPropagation()}>
                  {previewUrl && (
                    <Image
                      src={previewUrl}
                      alt="Preview of the selected image"
                      className="upload-preview-image"
                      width={320}
                      height={240}
                      unoptimized
                    />
                  )}
                  <div className="upload-preview-meta">
                    <span>
                      <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(2)} MB)
                    </span>
                    <button
                      type="button"
                      className="btn-remove-file"
                      onClick={handleClearFile}
                      aria-label="Remove the selected file"
                    >
                      ✕ Clear
                    </button>
                  </div>
                </div>
              )}
            </div>

            {error && <p className="upload-error" role="alert">{error}</p>}

            <button
              onClick={handleUpload}
              className="btn btn-primary upload-submit-btn"
              disabled={!file || loading}
              type="button"
            >
              Check authenticity
            </button>
          </>
        ) : (
          <div className="radar-hud-wrapper" role="status" aria-live="polite">
            <div className="radar-scanner-box" aria-hidden="true">
              <span className="radar-crosshair-h" />
              <span className="radar-crosshair-v" />
              <span className="radar-concentric-inner" />
              <div className="radar-sweep-beam" />
              <div className="radar-target-dot" />
            </div>

            <div className="radar-hud-telemetry">
              <div className="realtime-live-badge">
                <span className="realtime-pulse-dot" aria-hidden="true" /> {status}
              </div>
              <div className="hud-elapsed-counter">{formatElapsed(elapsedMs)}</div>
              <p className="hud-stream-caption">{JOB_STATUS_COPY[status]}</p>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
