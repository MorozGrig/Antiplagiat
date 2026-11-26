
const API_BASE_URL = 'http://localhost:8000/api/v1'

export interface AuthUser {
  id: string
  username: string
  email: string
  role: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

interface RegisterData {
  username: string
  email: string
  password: string
}

interface LoginData {
  username_or_email: string
  password: string
}



async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  const isFormData = options.body instanceof FormData

  // Content-Type нужен только при отправке тела запроса.
  // Для FormData браузер самостоятельно установит boundary.
  if (options.body != null && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  let data: unknown = null

  if (response.status !== 204) {
    const contentType = response.headers.get('content-type') ?? ''

    if (contentType.includes('application/json') || contentType.includes('+json')) {
      data = await response.json().catch(() => null)
    } else {
      const text = await response.text().catch(() => '')
      data = text ? { message: text } : null
    }
  }

  if (!response.ok) {
    const body = data as {
      detail?: unknown
      message?: unknown
    } | null

    const detail = body?.detail

    let message = `Ошибка ${response.status}: ${response.statusText}`

    if (typeof detail === 'string') {
      message = detail
    } else if (
      typeof detail === 'object' &&
      detail !== null &&
      'message' in detail &&
      typeof detail.message === 'string'
    ) {
      message = detail.message
    } else if (
      typeof detail === 'object' &&
      detail !== null &&
      'error' in detail &&
      typeof detail.error === 'string'
    ) {
      message = detail.error
    } else if (Array.isArray(detail)) {
      message = detail
        .map((item) =>
          typeof item?.msg === 'string' ? item.msg : null,
        )
        .filter(Boolean)
        .join('; ') || message
    } else if (typeof body?.message === 'string') {
      message = body.message
    }

    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  if (data === null) {
    throw new Error('Сервер вернул пустой или некорректный ответ.')
  }

  return data as T
}



export function register(data: RegisterData): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function login(data: LoginData): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export interface MaterialItem {
  id: string
  registration_number: string
  title: string
  category: string
  status: string
  processing_status: string
  uniqueness_score: number | null
  created_at: string
}


export interface SimilarityMatch {
  matched_material_id: string
  matched_registration_number: string
  matched_title: string
  similarity_percentage: number
  check_method: string
}

export interface MaterialDetail extends MaterialItem {
  author_id: string
  description: string | null
  tags: string[] | null
  sha256_hash: string
  file_type: string
  file_size_bytes: number
  similarity_matches: SimilarityMatch[]
  certificate_number: string | null
  certificate_issued_at: string | null
  certificate_status: string | null
}


export interface MaterialListResponse {
  items: MaterialItem[]
  total: number
  limit: number
  offset: number
}

export function getMaterials(
  token: string,
  limit = 20,
  offset = 0,
): Promise<MaterialListResponse> {
  validatePagination(limit, offset)

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  return request<MaterialListResponse>(
    `/materials?${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  )
}

export function getMaterial(
  token: string,
  materialId: string,
): Promise<MaterialDetail> {
  validateId(token, 'Токен авторизации')
  validateId(materialId, 'ID материала')

  return request<MaterialDetail>(
    `/materials/${encodeURIComponent(materialId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  )
}

export async function downloadMaterialCertificate(
  token: string,
  materialId: string,
): Promise<void> {
  validateId(token, 'Токен авторизации')
  validateId(materialId, 'ID материала')

  const response = await fetch(
    `${API_BASE_URL}/materials/${encodeURIComponent(materialId)}/certificate/download`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  )

  if (!response.ok) {
    const responseText = await response.text().catch(() => '')
    let message = `Ошибка скачивания сертификата: ${response.status}`

    if (responseText) {
      try {
        const data = JSON.parse(responseText)
        if (typeof data.detail === 'string') {
          message = data.detail
        } else if (typeof data.message === 'string') {
          message = data.message
        }
      } catch {
        // Если сервер вернул не JSON, оставляем стандартное сообщение.
      }
    }

    throw new Error(message)
  }

  const contentType = response.headers.get('content-type') ?? ''

  if (!contentType.toLowerCase().includes('application/pdf')) {
    throw new Error('Сервер вернул файл в неподдерживаемом формате.')
  }

  const blob = await response.blob()

  if (blob.size === 0) {
    throw new Error('Сервер вернул пустой PDF-файл.')
  }

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = `certificate-${materialId}.pdf`

  document.body.appendChild(link)
  link.click()
  link.remove()

  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export interface MaterialRegistrationResponse {
  material_id: string
  registration_number: string
  sha256_hash: string
  file_type: string
  file_size_bytes: number
  title: string
  status: string
  processing_status: string
  created_at: string
  task_id: string | null
}

const MAX_FILE_SIZE = 10 * 1024 * 1024

const ALLOWED_FILE_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.txt',
  '.jpg',
  '.jpeg',
  '.png',
  '.mp4',
  '.mov',
  '.avi',
  '.mkv',
]

function validateMaterialUpload(data: MaterialUploadData): void {
  if (!data.file) {
    throw new Error('Выберите файл для загрузки.')
  }

  if (data.file.size === 0) {
    throw new Error('Выбран пустой файл.')
  }

  if (data.file.size > MAX_FILE_SIZE) {
    throw new Error('Размер файла не должен превышать 10 МБ.')
  }

  const fileName = data.file.name.toLowerCase()
  const hasAllowedExtension = ALLOWED_FILE_EXTENSIONS.some(
    (extension) => fileName.endsWith(extension),
  )

  if (!hasAllowedExtension) {
    throw new Error('Формат файла не поддерживается.')
  }

  if (!data.title.trim() || data.title.trim().length > 255) {
    throw new Error('Название обязательно и должно содержать не более 255 символов.')
  }

  if (!data.category.trim() || data.category.trim().length > 100) {
    throw new Error('Категория обязательна и должна содержать не более 100 символов.')
  }

  if ((data.description?.length ?? 0) > 10000) {
    throw new Error('Описание не должно превышать 10000 символов.')
  }

  if ((data.tags?.length ?? 0) > 20) {
    throw new Error('Можно указать не более 20 тегов.')
  }

  if (data.tags?.some((tag) => !tag.trim() || tag.trim().length > 50)) {
    throw new Error('Каждый тег должен содержать от 1 до 50 символов.')
  }
}
export interface MaterialUploadData {
  file: File
  title: string
  category: string
  description?: string
  tags?: string[]
}

export function uploadMaterial(
  token: string,
  data: MaterialUploadData,
): Promise<MaterialRegistrationResponse> {
  validateId(token, 'Токен авторизации')
  validateMaterialUpload(data)

  const formData = new FormData()

  formData.append('file', data.file)
  formData.append('title', data.title.trim())
  formData.append('category', data.category.trim())

  if (data.description?.trim()) {
    formData.append('description', data.description.trim())
  }

  data.tags?.forEach((tag) => {
    formData.append('tags', tag.trim())
  })

  return request<MaterialRegistrationResponse>('/materials', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })
}

// ================================
// Административная панель
// ================================

export interface AdminStats {
  users_total: number
  materials_total: number
  materials_pending: number
  disputes_total: number
  disputes_pending: number
}

export interface AdminUser {
  id: string
  username: string
  email: string
  role: string
  status: string
  created_at: string
  updated_at: string
}

export interface AdminMaterial {
  id: string
  registration_number: string
  author_id: string
  title: string
  category: string
  status: string
  is_public: boolean
  processing_status: string
  uniqueness_score: number | null
  sha256_hash: string
  created_at: string
}

export interface ProcessingLogItem {
  id: string
  material_id: string
  step: string
  status: string
  details: unknown
  error_message: string | null
  started_at: string
  completed_at: string | null
}

// Получение общей статистики
export function getAdminStats(token: string): Promise<AdminStats> {
  return request<AdminStats>('/admin/stats', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

function validatePagination(limit: number, offset: number): void {
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    throw new Error('Количество записей должно быть от 1 до 100.')
  }

  if (!Number.isInteger(offset) || offset < 0) {
    throw new Error('Смещение не может быть отрицательным.')
  }
}
type UserStatus = 'active' | 'suspended' | 'banned'

type MaterialStatus =
  | 'active'
  | 'on_moderation'
  | 'archived'
  | 'blocked'

const USER_STATUSES: UserStatus[] = [
  'active',
  'suspended',
  'banned',
]

const MATERIAL_STATUSES: MaterialStatus[] = [
  'active',
  'on_moderation',
  'archived',
  'blocked',
]

function validateSearch(search: string): string {
  const normalized = search.trim()

  if (normalized.length > 100) {
    throw new Error('Поисковый запрос не должен превышать 100 символов.')
  }

  return normalized
}

function validateId(id: string, fieldName = 'Идентификатор'): void {
  if (!id || !id.trim()) {
    throw new Error(`${fieldName} не может быть пустым.`)
  }
}

function validateUserStatus(status: string): void {
  if (!USER_STATUSES.includes(status as UserStatus)) {
    throw new Error('Указан недопустимый статус пользователя.')
  }
}

function validateMaterialStatus(status: string): void {
  if (!MATERIAL_STATUSES.includes(status as MaterialStatus)) {
    throw new Error('Указан недопустимый статус материала.')
  }
}
// Получение списка пользователей
export function getAdminUsers(
  token: string,
  search = '',
  limit = 50,
  offset = 0,
): Promise<AdminUser[]> {
  validatePagination(limit, offset)
  const normalizedSearch = validateSearch(search)

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  if (normalizedSearch) {
    params.set('search', normalizedSearch)
  }

  return request<AdminUser[]>(`/admin/users?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

// Изменение статуса пользователя
export function updateAdminUser(
  token: string,
  userId: string,
  status: string,
): Promise<AdminUser> {
  validateId(userId, 'ID пользователя')
  validateUserStatus(status)

  return request<AdminUser>(
    `/admin/users/${encodeURIComponent(userId)}`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ status }),
    },
  )
}

// Получение списка материалов
export function getAdminMaterials(
  token: string,
  status = '',
  search = '',
  limit = 50,
  offset = 0,
): Promise<AdminMaterial[]> {
  validatePagination(limit, offset)
  const normalizedSearch = validateSearch(search)

  if (status) {
    validateMaterialStatus(status)
  }

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  if (status) {
    params.set('status', status)
  }

  if (normalizedSearch) {
    params.set('search', normalizedSearch)
  }

  return request<AdminMaterial[]>(`/admin/materials?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

// Изменение статуса и публичности материала
export function updateAdminMaterial(
  token: string,
  materialId: string,
  data: {
    status?: string
    is_public?: boolean
  },
): Promise<AdminMaterial> {
  validateId(materialId, 'ID материала')

  if (!data || Object.keys(data).length === 0) {
    throw new Error('Не указаны изменения материала.')
  }

  if (
    data.status !== undefined &&
    data.status !== ''
  ) {
    validateMaterialStatus(data.status)
  }

  if (
    data.is_public !== undefined &&
    typeof data.is_public !== 'boolean'
  ) {
    throw new Error('Некорректное значение публичности материала.')
  }

  return request<AdminMaterial>(
    `/admin/materials/${encodeURIComponent(materialId)}`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    },
  )
}

// Получение журнала обработки
export function getAdminProcessingLog(
  token: string,
  materialId?: string,
  limit = 100,
  offset = 0,
): Promise<ProcessingLogItem[]> {
  validatePagination(limit, offset)
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  if (materialId) {
    params.set('material_id', materialId)
  }

  return request<ProcessingLogItem[]>(`/admin/processing-log?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

export interface VerificationResult {
  verified: boolean
  certificate_number: string
  registration_number: string
  material_title: string
  category: string
  author_name: string
  sha256_hash: string
  uniqueness_score: number
  issued_at: string
  certificate_status: string
}

function validateVerificationNumber(value: string): string {
  const normalized = value.trim()

  if (!normalized) {
    throw new Error('Введите номер для проверки.')
  }

  if (normalized.length > 100) {
    throw new Error('Номер не должен превышать 100 символов.')
  }

  return normalized
}

export async function verifyCertificate(
  certificateNumber: string,
): Promise<VerificationResult> {
  const normalized = validateVerificationNumber(certificateNumber)

  return request<VerificationResult>(
    `/public/verification/${encodeURIComponent(normalized)}`,
  )
}

export async function verifyRegistration(
  registrationNumber: string,
): Promise<VerificationResult> {
  const normalized = validateVerificationNumber(registrationNumber)

  return request<VerificationResult>(
    `/public/verification/registration/${encodeURIComponent(normalized)}`,
  )
}

export async function verifyFile(file: File): Promise<VerificationResult> {
  const MAX_FILE_SIZE = 10 * 1024 * 1024

  if (file.size === 0) {
    throw new Error('Выбран пустой файл.')
  }

  if (file.size > MAX_FILE_SIZE) {
    throw new Error('Размер файла не должен превышать 10 МБ.')
  }

  const formData = new FormData()
  formData.append('file', file)

  return request<VerificationResult>('/public/verification/file', {
    method: 'POST',
    body: formData,
  })
}
