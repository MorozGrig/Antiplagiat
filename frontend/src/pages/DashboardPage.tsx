
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  FileText,
  LogOut,
  ShieldCheck,
  User,
  Upload,
  ChevronDown,
  ChevronUp,
  Search,
  LoaderCircle,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  getMaterials,
  getMaterial,
  uploadMaterial,
  type MaterialItem,
  type MaterialDetail,
} from '../services/api'
import '../App.css'


function materialStatus(status: string) {
  const statuses: Record<string, string> = {
    on_moderation: 'На модерации',
    active: 'Активен',
    archived: 'В архиве',
    blocked: 'Заблокирован',
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

  const [expandedMaterialId, setExpandedMaterialId] = useState<string | null>(null)
  const [materialDetails, setMaterialDetails] = useState<Record<string, MaterialDetail>>({})
  const [detailsLoading, setDetailsLoading] = useState<string | null>(null)
  const [detailsErrors, setDetailsErrors] = useState<Record<string, string>>({})

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

  
  
async function handleToggleMaterial(materialId: string) {
  if (expandedMaterialId === materialId) {
    setExpandedMaterialId(null)
    return
  }

  setExpandedMaterialId(materialId)

  // Если подробности уже загружены, повторный запрос не нужен.
  if (materialDetails[materialId] || !token) {
    return
  }

  try {
    setDetailsLoading(materialId)

    setDetailsErrors((previous) => ({
      ...previous,
      [materialId]: '',
    }))

    const details = await getMaterial(token, materialId)

    setMaterialDetails((previous) => ({
      ...previous,
      [materialId]: details,
    }))
  } catch (err) {
    setDetailsErrors((previous) => ({
      ...previous,
      [materialId]:
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить результаты проверки.',
    }))
  } finally {
    setDetailsLoading(null)
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

  <div className="dashboard-header-actions">
    {user?.role === 'admin' && (
      <Link to="/admin" className="button button-primary">
        <ShieldCheck size={17} />
        Админ-панель
      </Link>
    )}

    <button className="dashboard-logout" onClick={handleLogout}>
      <LogOut size={17} />
      Выйти
    </button>
  </div>
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


<div className="materials-section">
  <div className="materials-section-heading">
    <div>
      <span className="materials-section-kicker">МОЯ БИБЛИОТЕКА</span>
      <h2>Ваши материалы</h2>
      <p>Зарегистрированные работы и результаты проверки уникальности.</p>
    </div>

    <div className="materials-total">
      <FileText size={18} />
      <span>{materials.length} материалов</span>
    </div>
  </div>

  {loading && (
    <p className="materials-message">Загружаем материалы...</p>
  )}

  {error && (
    <p className="materials-error">{error}</p>
  )}

  {!loading && !error && materials.length === 0 && (
    <div className="materials-empty">
      <FileText size={34} />
      <h3>Пока здесь пусто</h3>
      <p>Зарегистрируйте первый авторский материал, чтобы увидеть его в этом разделе.</p>
    </div>
  )}

  {!loading && !error && materials.length > 0 && (
    <div className="materials-list">
      {materials.map((material) => {
        const isExpanded = expandedMaterialId === material.id
        const details = materialDetails[material.id]
        const isDetailsLoading = detailsLoading === material.id
        const detailsError = detailsErrors[material.id]

        const uniqueness = material.uniqueness_score
        const uniquenessValue =
          uniqueness == null
            ? null
            : Math.min(100, Math.max(0, uniqueness))

        return (
          <article className="material-card" key={material.id}>
            <div className="material-card-main">
              <div className="material-card-icon">
                <FileText size={23} />
              </div>

              <div className="material-card-content">
                <div className="material-card-title-row">
                  <h3>{material.title}</h3>

                  <span className={`material-status status-${material.status}`}>
                    {materialStatus(material.status)}
                  </span>
                </div>

                <div className="material-card-meta">
                  <span>№ {material.registration_number}</span>
                  <span>{material.category}</span>
                  <span>
                    {new Date(material.created_at).toLocaleDateString('ru-RU')}
                  </span>
                </div>

                <div className="material-processing">
                  <span className={`processing-indicator processing-${material.processing_status}`} />
                  {processingStatus(material.processing_status)}
                </div>

                <div className="material-uniqueness">
                  <div className="material-uniqueness-heading">
                    <span>Уникальность текста</span>
                    <strong>
                      {uniquenessValue == null
                        ? 'Ожидается проверка'
                        : `${uniquenessValue.toFixed(2)}%`}
                    </strong>
                  </div>

                  <div className="material-progress-track">
                    <div
                      className="material-progress-fill"
                      style={{
                        width: `${uniquenessValue ?? 0}%`,
                      }}
                    />
                  </div>
                </div>

                {material.processing_status === 'completed' && (
                  <button
                    type="button"
                    className="material-details-button"
                    onClick={() => handleToggleMaterial(material.id)}
                  >
                    <Search size={16} />
                    {isExpanded ? 'Скрыть результаты' : 'Посмотреть совпадения'}
                    {isExpanded
                      ? <ChevronUp size={17} />
                      : <ChevronDown size={17} />}
                  </button>
                )}
              </div>
            </div>

            {isExpanded && (
              <div className="material-details">
                {isDetailsLoading && (
                  <p className="material-details-message">
                    <LoaderCircle size={17} className="material-spinner" />
                    Загружаем результаты проверки...
                  </p>
                )}

                {detailsError && (
                  <p className="material-details-error">{detailsError}</p>
                )}

                {details && !isDetailsLoading && (
                  <>
                    <h4>Найденные совпадения</h4>

                    {details.similarity_matches.length === 0 ? (
                      <p className="material-no-matches">
                        Совпадений с другими зарегистрированными материалами не обнаружено.
                      </p>
                    ) : (
                      <div className="similarity-list">
                        {details.similarity_matches.map((match) => (
                          <div
                            className="similarity-item"
                            key={match.matched_material_id}
                          >
                            <div className="similarity-item-info">
                              <strong>{match.matched_title}</strong>
                              <span>
                                № {match.matched_registration_number}
                              </span>
                              <small>
                                Метод проверки: {match.check_method}
                              </small>
                            </div>

                            <div className="similarity-percentage">
                              {match.similarity_percentage.toFixed(2)}%
                              <span>сходства</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </article>
        )
      })}
    </div>
  )}
</div>
      </section>
    </main>
  )
}
