
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Search, ShieldCheck, FileCheck2, LoaderCircle } from 'lucide-react'
import {
  verifyCertificate,
  verifyRegistration,
  verifyFile,
  type VerificationResult,
} from '../services/api'
import '../App.css'

export default function VerifyPage() {
  const [number, setNumber] = useState('')
  const [searchType, setSearchType] = useState<'certificate' | 'registration'>('certificate')
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [file, setFile] = useState<File | null>(null)



  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (loading) return
    setError('')
    setResult(null)

    const value = number.trim()

    if (!value) {
      setError('Введите номер для проверки.')
      return
    }

    if (value.length > 100) {
      setError('Номер не должен превышать 100 символов.')
      return
    }

    try {
      setLoading(true)
      const response =
        searchType === 'certificate'
          ? await verifyCertificate(value)
          : await verifyRegistration(value)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить проверку.')
    } finally {
      setLoading(false)
    }
  }

  async function handleFileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (loading) return
    setError('')
    setResult(null)

    if (!file) {
      setError('Выберите файл для проверки.')
      return
    }

    if (file.size === 0) {
      setError('Выбран пустой файл.')
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('Размер файла не должен превышать 10 МБ.')
      return
    }
const allowedExtensions = [
  'pdf',
  'docx',
  'txt',
  'jpg',
  'jpeg',
  'png',
  'mp4',
  'mov',
  'avi',
  'mkv',
]

const extension = file.name.split('.').pop()?.toLowerCase()

if (!extension || !allowedExtensions.includes(extension)) {
  setError('Недопустимый формат файла.')
  return
}

    try {
      setLoading(true)
      const response = await verifyFile(file)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось проверить файл.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-top">
        <Link to="/" className="auth-back">
          <ArrowLeft size={18} />
          На главную
        </Link>

        <Link to="/" className="brand">
          <span className="brand-mark">
            <ShieldCheck size={21} />
          </span>
          АвторРеестр
        </Link>
      </div>

      <section className="auth-card verify-card">
        <div className="auth-icon">
          <Search size={26} />
        </div>

        <p className="eyebrow">ПУБЛИЧНЫЙ СЕРВИС</p>
        <h1>Проверка свидетельства</h1>
        <p className="auth-description">
          Проверьте сведения о зарегистрированном авторском материале
          по номеру свидетельства или регистрационному номеру.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="verify-type">Способ проверки</label>
          <select
            id="verify-type"
            value={searchType}
            onChange={(event) =>
              setSearchType(event.target.value as 'certificate' | 'registration')
            }
          >
            <option value="certificate">По номеру свидетельства</option>
            <option value="registration">По регистрационному номеру</option>
          </select>

          <label htmlFor="verify-number">Номер</label>
          <input
            id="verify-number"
            type="text"
            value={number}
            onChange={(event) => setNumber(event.target.value)}
            placeholder="Введите номер"
            maxLength={100}
            required
          />

          {error && <div className="auth-error" role="alert">{error}</div>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? (
              <>
                <LoaderCircle size={17} className="material-spinner" />
                Проверяем...
              </>
            ) : (
              <>
                <Search size={17} />
                Проверить
              </>
            )}
          </button>
        </form>

<div className="verify-file-section">
  <div className="verify-file-divider">
    <span>ИЛИ</span>
  </div>

  <form onSubmit={handleFileSubmit} className="auth-form">
    <label htmlFor="verify-file">Проверить по файлу</label>

    <input
      id="verify-file"
      type="file"
      accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.mp4,.mov,.avi,.mkv"
      onChange={(event) => {
        setFile(event.target.files?.[0] ?? null)
        setError('')
        setResult(null)
      }}
      disabled={loading}
    />

    <p className="auth-description">
      Поддерживаются PDF, DOCX, TXT, JPG, PNG, MP4, MOV, AVI и MKV.
      Максимальный размер — 10 МБ.
    </p>

    <button
      className="auth-submit"
      type="submit"
      disabled={loading || !file}
    >
      {loading ? (
        <>
          <LoaderCircle size={17} className="material-spinner" />
          Проверяем...
        </>
      ) : (
        <>
          <FileCheck2 size={17} />
          Проверить файл
        </>
      )}
    </button>
  </form>
</div>

        {result && (
          <div className="verify-result" role="status">
            <FileCheck2 size={28} />
            <h2>Сведения найдены</h2>

            <p><strong>Статус:</strong> {result.certificate_status}</p>
            <p><strong>Свидетельство:</strong> {result.certificate_number}</p>
            <p><strong>Регистрационный номер:</strong> {result.registration_number}</p>
            <p><strong>Материал:</strong> {result.material_title}</p>
            <p><strong>Категория:</strong> {result.category}</p>
            <p><strong>Автор:</strong> {result.author_name}</p>
            <p><strong>Дата выдачи:</strong> {new Date(result.issued_at).toLocaleDateString('ru-RU')}</p>
            <p><strong>Уникальность:</strong> {result.uniqueness_score}%</p>
            <p><strong>SHA-256:</strong></p>
            <code className="verify-hash">{result.sha256_hash}</code>

            <p className="verify-disclaimer">
              Результат подтверждает наличие записи в реестре и не является
              государственным документом, удостоверяющим авторские права.
            </p>
          </div>
        )}
      </section>

      <p className="auth-footer">
        АвторРеестр · Публичная проверка сведений
      </p>
    </main>
  )
}
