
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

  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data?.detail

    const message =
      typeof detail === 'string'
        ? detail
        : typeof detail?.message === 'string'
          ? detail.message
          : typeof detail?.error === 'string'
            ? detail.error
            : typeof data?.message === 'string'
              ? data.message
              : `Ошибка ${response.status}: ${response.statusText}`

    throw new Error(message)
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
  return request<MaterialListResponse>(
    `/materials?limit=${limit}&offset=${offset}`,
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
  return request<MaterialDetail>(`/materials/${materialId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
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
  const formData = new FormData()

  formData.append('file', data.file)
  formData.append('title', data.title)
  formData.append('category', data.category)

  if (data.description?.trim()) {
    formData.append('description', data.description.trim())
  }

  data.tags?.forEach((tag) => {
    if (tag.trim()) {
      formData.append('tags', tag.trim())
    }
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

// Получение списка пользователей
export function getAdminUsers(
  token: string,
  search = '',
  limit = 50,
  offset = 0,
): Promise<AdminUser[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  if (search.trim()) {
    params.set('search', search.trim())
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
  return request<AdminUser>(`/admin/users/${userId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ status }),
  })
}

// Получение списка материалов
export function getAdminMaterials(
  token: string,
  status = '',
  search = '',
  limit = 50,
  offset = 0,
): Promise<AdminMaterial[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  if (status) {
    params.set('status', status)
  }

  if (search.trim()) {
    params.set('search', search.trim())
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
  return request<AdminMaterial>(`/admin/materials/${materialId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  })
}

// Получение журнала обработки
export function getAdminProcessingLog(
  token: string,
  materialId?: string,
  limit = 100,
  offset = 0,
): Promise<ProcessingLogItem[]> {
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

