'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiUrl } from '@/lib/api'

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) {
    return err.message
  }
  return 'An unexpected error occurred during analysis.'
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0])
      setError('')
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a media file to verify.')
      return
    }

    setLoading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/v1/upload/'), {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let detail = `Verification failed. Server returned ${response.status}`
        try {
          const payload = await response.json()
          if (payload?.detail) {
            detail = payload.detail
          }
        } catch {}
        throw new Error(detail)
      }

      const report = await response.json()
      // report.id maps to ledger_id
      router.push(`/report/${report.id}`)
    } catch (err: unknown) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main id="main-content" className="page page-upload">
      <section className="upload-intro">
        <p className="eyebrow">Verification Intake</p>
        <h1 className="page-title">Run Verification</h1>
        <p className="upload-description">
          Upload an image, audio, or video file to run against the 5-layer Multi-Signal Trust Engine.
        </p>
      </section>

      <section className="upload-shell card-soft">
        {!loading ? (
          <>
            <div className="upload-guidance">
              <h2>Select media file</h2>
              <p>Supported formats: JPEG, PNG, WEBP, MP4, MP3. Maximum upload size: 50 MB.</p>
            </div>

            <input
              type="file"
              id="file-upload"
              className="sr-only-input"
              onChange={handleFileChange}
            />

            <label htmlFor="file-upload" className="btn btn-secondary upload-file-trigger">
              Select File
            </label>

            {file && (
              <p className="upload-selected-file">
                Selected: <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}

            {error && <p className="upload-error" role="alert">{error}</p>}

            <button
              onClick={handleUpload}
              className="btn btn-primary upload-submit-btn"
              disabled={!file || loading}
              type="button"
            >
              Scan Authenticity
            </button>
          </>
        ) : (
          <div className="upload-loading-state" aria-live="polite">
            <div className="spinner"></div>
            <div>
              <h3>Analyzing Media Vector...</h3>
              <p>Processing Behavioral Signals, Deepfake Artifacts, and C2PA Matrix...</p>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
