
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  FileText,
  LogOut,
  ShieldCheck,
  User,
  Upload,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  getMaterials,
  uploadMaterial,
  type MaterialItem,
} from '../services/api'
import '../App.css'

function materialStatus(status: string) {
  const statuses: Record<string, string> = {
    on_moderation: 'На модерации',
    approved: 'Одобрен',
    rejected: 'Отклонён',
  }
  return statuses[status] || status
}

function processingStatus(status: string) {
  const statuses: Record<string, string> = {
    pending: 'В очереди',
    processing: 'Обрабатывается',
    completed: 'Завершена',
    failed: 'Ошибка',
  }
  return statuses[status] || status
}

export default function DashboardPage() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()

  const [materials, setMaterials] = useState<MaterialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')

  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }

    let cancelled = false

    async function loadMaterials() {
      try {
        setLoading(true)
        setError('')

        const result = await getMaterials(token!)
        if (!cancelled) {
          setMaterials(result.items)
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Не удалось загрузить материалы.',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadMaterials()

    return () => {
      cancelled = true
    }
  }, [token])

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!token || !file) {
      setUploadError('Выберите файл для загрузки.')
      return
    }

    try {
      setUploading(true)
      setUploadError('')
      setSuccessMessage('')

      const result = await uploadMaterial(token, {
        file,
        title: title.trim(),
        category: category.trim(),
        description: description.trim(),
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      })

      setSuccessMessage(
        `Материал зарегистрирован! Номер: ${result.registration_number}`,
      )

      setFile(null)
      setTitle('')
      setCategory('')
      setDescription('')
      setTags('')

      const fileInput = document.getElementById(
        'material-file',
      ) as HTMLInputElement | null

      if (fileInput) {
        fileInput.value = ''
      }

      const updatedMaterials = await getMaterials(token)
      setMaterials(updatedMaterials.items)
    } catch (err) {
      setUploadError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить материал.',
      )
    } finally {
      setUploading(false)
    }
  }

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <main className="dashboard-page">
      <header className="dashboard-header">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <ShieldCheck size={21} />
          </span>
          АвторРеестр
        </Link>

        <button className="dashboard-logout" onClick={handleLogout}>
          <LogOut size={17} />
          Выйти
        </button>
      </header>

      <section className="dashboard-content">
        <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
        <h1>Здравствуйте, {user?.username || 'пользователь'}!</h1>
        <p className="dashboard-description">
          Здесь вы можете просматривать свои авторские материалы
          и результаты проверки уникальности.
        </p>

        <div className="dashboard-user-card">
          <div className="dashboard-user-icon">
            <User size={24} />
          </div>
          <div>
            <strong>{user?.username}</strong>
            <p>{user?.email}</p>
            <span>Роль: {user?.role}</span>
          </div>
        </div>

        <div className="dashboard-placeholder">
          <div className="dashboard-placeholder-icon">
            <Upload size={27} />
          </div>

          <h2>Зарегистрировать материал</h2>
          <p>Заполните информацию и выберите файл для загрузки.</p>

          <form onSubmit={handleUpload} className="material-upload-form">
            <label htmlFor="material-title">Название материала</label>
            <input
              id="material-title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={255}
              required
              placeholder="Например, Научная статья"
            />

            <label htmlFor="material-category">Категория</label>
            <input
              id="material-category"
              type="text"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              maxLength={100}
              required
              placeholder="Например, Научная работа"
            />

            <label htmlFor="material-description">Описание</label>
            <textarea
              id="material-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={10000}
              placeholder="Краткое описание материала"
              rows={4}
            />

            <label htmlFor="material-tags">Теги</label>
            <input
              id="material-tags"
              type="text"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="исследование, наука, статья"
            />
            <small>Указывайте теги через запятую.</small>

            <label htmlFor="material-file">Файл материала</label>
            <input
              id="material-file"
              type="file"
              onChange={(event) =>
                setFile(event.target.files?.[0] || null)
              }
              required
            />

            {file && <p>Выбран файл: {file.name}</p>}

            {uploadError && <p role="alert">{uploadError}</p>}

            {successMessage && (
              <p role="status">{successMessage}</p>
            )}

            <button type="submit" disabled={uploading}>
              {uploading ? 'Загружаем...' : 'Зарегистрировать материал'}
            </button>
          </form>
        </div>

        <div className="dashboard-placeholder">
          <div className="dashboard-placeholder-icon">
            <FileText size={27} />
          </div>

          <h2>Ваши материалы</h2>

          {loading && <p>Загружаем материалы...</p>}

          {error && <p>{error}</p>}

          {!loading && !error && materials.length === 0 && (
            <p>Пока у вас нет зарегистрированных материалов.</p>
          )}

          {!loading && !error && materials.length > 0 && (
            <div className="materials-list">
              <p>Всего материалов: {materials.length}</p>

              {materials.map((material) => (
                <article className="material-card" key={material.id}>
                  <h3>{material.title}</h3>
                  <p>Номер регистрации: {material.registration_number}</p>
                  <p>Категория: {material.category}</p>
                  <p>Статус: {materialStatus(material.status)}</p>
                  <p>
                    Проверка: {processingStatus(material.processing_status)}
                  </p>
                  <p>
                    Уникальность:{' '}
                    {material.uniqueness_score != null
                      ? `${material.uniqueness_score}%`
                      : 'Ещё не определена'}
                  </p>
                  <p>
                    Дата регистрации:{' '}
                    {new Date(material.created_at).toLocaleDateString('ru-RU')}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
