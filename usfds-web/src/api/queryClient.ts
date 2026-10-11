import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 phút cache dữ liệu
      gcTime: 1000 * 60 * 30, // 30 phút dọn dẹp bộ nhớ
      retry: 1, // Thử lại 1 lần nếu gặp lỗi mạng
      refetchOnWindowFocus: false, // Không tự refetch khi chuyển qua lại cửa sổ desktop
    },
    mutations: {
      retry: false,
    },
  },
});
