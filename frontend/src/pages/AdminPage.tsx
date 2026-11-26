
import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  FileText,
  Scale,
  Users,
  Clock,
  ShieldCheck,
  RefreshCw,
  Search,
  Eye,
  EyeOff,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  getAdminStats,
  getAdminUsers,
  updateAdminUser,
  getAdminMaterials,
  updateAdminMaterial,
  type AdminStats,
  type AdminUser,
  type AdminMaterial,
} from '../services/api'

type AdminTab = 'users' | 'materials'

const userStatusLabels: Record<string, string> = {
  active: 'Активен',
  suspended: 'Приостановлен',
  banned: 'Заблокирован',
}

const materialStatusLabels: Record<string, string> = {
  active: 'Активен',
  on_moderation: 'На модерации',
  archived: 'В архиве',
  blocked: 'Заблокирован',
}

export default function AdminPage() {
  const { token, user, logout } = useAuth()

  const [activeTab, setActiveTab] = useState<AdminTab>('users')

  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [materials, setMaterials] = useState<AdminMaterial[]>([])

  const [userSearch, setUserSearch] = useState('')
  const [materialSearch, setMaterialSearch] = useState('')
  const [materialStatusFilter, setMaterialStatusFilter] = useState('')

  const [loading, setLoading] = useState(true)
  const [usersLoading, setUsersLoading] = useState(false)
  const [materialsLoading, setMaterialsLoading] = useState(false)

  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')

  const [savingUserId, setSavingUserId] = useState<string | null>(null)
  const [savingMaterialId, setSavingMaterialId] = useState<string | null>(null)

  async function loadStats() {
    if (!token) return

    try {
      setLoading(true)
      setError('')
      const data = await getAdminStats(token)
      setStats(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить статистику.')
    } finally {
      setLoading(false)
    }
  }

  async function loadUsers(searchValue = userSearch) {
    if (!token) return

    try {
      setUsersLoading(true)
      setActionError('')
      const data = await getAdminUsers(token, searchValue)
      setUsers(data)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось загрузить пользователей.')
    } finally {
      setUsersLoading(false)
    }
  }

  async function loadMaterials(
    searchValue = materialSearch,
    statusValue = materialStatusFilter,
  ) {
    if (!token) return

    try {
      setMaterialsLoading(true)
      setActionError('')
      const data = await getAdminMaterials(
        token,
        statusValue,
        searchValue,
      )
      setMaterials(data)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось загрузить материалы.')
    } finally {
      setMaterialsLoading(false)
    }
  }

  async function handleUserStatusChange(
    selectedUser: AdminUser,
    newStatus: string,
  ) {
    if (!token || newStatus === selectedUser.status) return

    const confirmed = window.confirm(
      `Изменить статус пользователя ${selectedUser.username} на «${userStatusLabels[newStatus]}»?`,
    )

    if (!confirmed) return

    try {
      setSavingUserId(selectedUser.id)
      setActionError('')

      const updatedUser = await updateAdminUser(
        token,
        selectedUser.id,
        newStatus,
      )

      setUsers((current) =>
        current.map((item) =>
          item.id === updatedUser.id ? updatedUser : item,
        ),
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось изменить статус пользователя.')
    } finally {
      setSavingUserId(null)
    }
  }

  async function handleMaterialStatusChange(
    selectedMaterial: AdminMaterial,
    newStatus: string,
  ) {
    if (!token || newStatus === selectedMaterial.status) return

    const confirmed = window.confirm(
      `Изменить статус материала «${selectedMaterial.title}» на «${materialStatusLabels[newStatus]}»?`,
    )

    if (!confirmed) return

    try {
      setSavingMaterialId(selectedMaterial.id)
      setActionError('')

      const updatedMaterial = await updateAdminMaterial(
        token,
        selectedMaterial.id,
        { status: newStatus },
      )

      setMaterials((current) =>
        current.map((item) =>
          item.id === updatedMaterial.id ? updatedMaterial : item,
        ),
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось изменить статус материала.')
    } finally {
      setSavingMaterialId(null)
    }
  }

  async function handleMaterialVisibilityChange(
    selectedMaterial: AdminMaterial,
  ) {
    if (!token) return

    const newVisibility = !selectedMaterial.is_public

    const confirmed = window.confirm(
      `${newVisibility ? 'Опубликовать' : 'Скрыть'} материал «${selectedMaterial.title}»?`,
    )

    if (!confirmed) return

    try {
      setSavingMaterialId(selectedMaterial.id)
      setActionError('')

      const updatedMaterial = await updateAdminMaterial(
        token,
        selectedMaterial.id,
        { is_public: newVisibility },
      )

      setMaterials((current) =>
        current.map((item) =>
          item.id === updatedMaterial.id ? updatedMaterial : item,
        ),
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось изменить публичность материала.')
    } finally {
      setSavingMaterialId(null)
    }
  }

  useEffect(() => {
    void loadStats()
    void loadUsers('')
  }, [token])

  useEffect(() => {
    if (activeTab === 'materials' && materials.length === 0) {
      void loadMaterials()
    }
  }, [activeTab, token])

  const cards = [
    { title: 'Пользователи', value: stats?.users_total, icon: Users },
    { title: 'Материалы', value: stats?.materials_total, icon: FileText },
    { title: 'Всего споров', value: stats?.disputes_total, icon: Scale },
    { title: 'Материалы на модерации', value: stats?.materials_pending, icon: Clock },
  ]

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div className="container dashboard-header-inner">
          <Link to="/" className="brand">
            <span className="brand-icon">
              <ShieldCheck size={23} />
            </span>
            <span className="brand-name">
              Автор<span>Реестр</span>
            </span>
          </Link>

          <div className="dashboard-user">
            <span>{user?.username}</span>
            <button
              className="button button-outline button-small"
              onClick={logout}
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main className="container dashboard-main">
        <div className="dashboard-welcome">
          <div>
            <span className="section-kicker">УПРАВЛЕНИЕ ПЛАТФОРМОЙ</span>
            <h1>Панель администратора</h1>
            <p>Обзор состояния реестра и административных показателей.</p>
          </div>

          <button
            className="button button-outline"
            onClick={() => {
              void loadStats()
              if (activeTab === 'users') {
                void loadUsers()
              } else {
                void loadMaterials()
              }
            }}
            disabled={loading || usersLoading || materialsLoading}
          >
            <RefreshCw size={17} />
            Обновить
          </button>
        </div>

        {error && <div className="materials-error">{error}</div>}

        <section className="admin-stats-grid">
          {cards.map((card) => {
            const Icon = card.icon

            return (
              <article className="admin-stat-card" key={card.title}>
                <div className="admin-stat-icon">
                  <Icon size={23} />
                </div>
                <span>{card.title}</span>
                <strong>{loading ? '...' : card.value ?? 0}</strong>
              </article>
            )
          })}
        </section>

        <nav className="admin-tabs">
          <button
            className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            <Users size={18} />
            Пользователи
          </button>

          <button
            className={`admin-tab ${activeTab === 'materials' ? 'active' : ''}`}
            onClick={() => setActiveTab('materials')}
          >
            <FileText size={18} />
            Материалы
          </button>
        </nav>

        {actionError && (
          <div className="materials-error">{actionError}</div>
        )}

        {activeTab === 'users' && (
          <section className="admin-users-section">
            <div className="admin-section-heading">
              <div>
                <span className="section-kicker">УПРАВЛЕНИЕ ДОСТУПОМ</span>
                <h2>Пользователи</h2>
                <p>Просмотр аккаунтов и управление их статусами.</p>
              </div>
            </div>

            <form
              className="admin-search"
              onSubmit={(event) => {
                event.preventDefault()
                void loadUsers(userSearch)
              }}
            >
              <Search size={18} />
              <input
                type="search"
                placeholder="Поиск по имени или email"
                value={userSearch}
                onChange={(event) => setUserSearch(event.target.value)}
              />
              <button
                className="button button-primary button-small"
                type="submit"
                disabled={usersLoading}
              >
                Найти
              </button>
            </form>

            {usersLoading ? (
              <p>Загрузка пользователей...</p>
            ) : users.length === 0 ? (
              <p>Пользователи не найдены.</p>
            ) : (
              <div className="admin-table-wrapper">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Пользователь</th>
                      <th>Email</th>
                      <th>Роль</th>
                      <th>Статус</th>
                      <th>Дата регистрации</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((item) => (
                      <tr key={item.id}>
                        <td>{item.username}</td>
                        <td>{item.email}</td>
                        <td>{item.role}</td>
                        <td>
                          <select
                            value={item.status}
                            disabled={savingUserId === item.id || item.id === user?.id}
                            onChange={(event) =>
                              void handleUserStatusChange(item, event.target.value)
                            }
                          >
                            <option value="active">Активен</option>
                            <option value="suspended">Приостановлен</option>
                            <option value="banned">Заблокирован</option>
                          </select>
                          {savingUserId === item.id && <span> Сохранение...</span>}
                        </td>
                        <td>
                          {new Date(item.created_at).toLocaleDateString('ru-RU')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {activeTab === 'materials' && (
          <section className="admin-users-section">
            <div className="admin-section-heading">
              <div>
                <span className="section-kicker">УПРАВЛЕНИЕ РЕЕСТРОМ</span>
                <h2>Материалы</h2>
                <p>Поиск, модерация и управление публичностью материалов.</p>
              </div>
            </div>

            <form
              className="admin-search"
              onSubmit={(event) => {
                event.preventDefault()
                void loadMaterials(materialSearch, materialStatusFilter)
              }}
            >
              <Search size={18} />
              <input
                type="search"
                placeholder="Название или регистрационный номер"
                value={materialSearch}
                onChange={(event) => setMaterialSearch(event.target.value)}
              />
              <button
                className="button button-primary button-small"
                type="submit"
                disabled={materialsLoading}
              >
                Найти
              </button>
            </form>

            <div className="admin-material-filters">
              <label htmlFor="material-status-filter">Статус материала</label>
              <select
                id="material-status-filter"
                value={materialStatusFilter}
                disabled={materialsLoading}
                onChange={(event) => {
                  const value = event.target.value
                  setMaterialStatusFilter(value)
                  void loadMaterials(materialSearch, value)
                }}
              >
                <option value="">Все статусы</option>
                <option value="active">Активен</option>
                <option value="on_moderation">На модерации</option>
                <option value="archived">В архиве</option>
                <option value="blocked">Заблокирован</option>
              </select>
            </div>

            {materialsLoading ? (
              <p>Загрузка материалов...</p>
            ) : materials.length === 0 ? (
              <p>Материалы не найдены.</p>
            ) : (
              <div className="admin-table-wrapper">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Регистрационный номер</th>
                      <th>Название</th>
                      <th>Категория</th>
                      <th>Уникальность</th>
                      <th>Обработка</th>
                      <th>Статус</th>
                      <th>Публичность</th>
                      <th>Дата регистрации</th>
                    </tr>
                  </thead>
                  <tbody>
                    {materials.map((item) => (
                      <tr key={item.id}>
                        <td>{item.registration_number}</td>
                        <td>{item.title}</td>
                        <td>{item.category}</td>
                        <td>
                          {item.uniqueness_score === null
                            ? '—'
                            : `${item.uniqueness_score.toFixed(2)}%`}
                        </td>
                        <td>{item.processing_status}</td>
                        <td>
                          <select
                            value={item.status}
                            disabled={savingMaterialId === item.id}
                            onChange={(event) =>
                              void handleMaterialStatusChange(item, event.target.value)
                            }
                          >
                            {Object.entries(materialStatusLabels).map(([value, label]) => (
                              <option value={value} key={value}>{label}</option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <button
                            className="button button-outline button-small"
                            disabled={savingMaterialId === item.id}
                            onClick={() => void handleMaterialVisibilityChange(item)}
                          >
                            {item.is_public ? (
                              <>
                                <Eye size={15} /> Публичный
                              </>
                            ) : (
                              <>
                                <EyeOff size={15} /> Скрытый
                              </>
                            )}
                          </button>
                        </td>
                        <td>
                          {new Date(item.created_at).toLocaleDateString('ru-RU')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        <Link to="/dashboard" className="button button-text">
          <ArrowLeft size={17} />
          Вернуться в личный кабинет
        </Link>
      </main>
    </div>
  )
}
