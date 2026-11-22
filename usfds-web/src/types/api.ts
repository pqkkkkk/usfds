/**
 * API Response & Error contracts matching usfds-server backend standards
 */

export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data: T;
  error?: string | null;
  code?: number;
  timestamp?: string;
}

export interface ResourceOwner {
  user_id: string;
  username: string;
  full_name?: string | null;
}

export interface CursorPage<T> {
  items: T[];
  nextCursor: string | null;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages?: number;
}

export interface ApiError {
  message: string;
  statusCode?: number;
  details?: unknown;
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  params?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
}
