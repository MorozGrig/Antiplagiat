
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
        : 'Не удалось выполнить запрос. Проверьте введённые данные.'

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


