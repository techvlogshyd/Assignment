import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginPage } from "./pages/Login";
import { DashboardPage } from "./pages/Dashboard";
import { OrdersPage } from "./pages/Orders";
import { OrderDetailPage } from "./pages/OrderDetail";
import { UploadPage } from "./pages/Upload";
import { ProtectedRoute } from "./pages/ProtectedRoute";
import { clearToken, isAuthenticated } from "./hooks/useAuth";

const queryClient = new QueryClient();

function NavBar() {
  const authed = isAuthenticated();
  return (
    <nav className="bg-white border-b px-6 py-3 flex items-center justify-between">
      <Link to="/" className="font-semibold text-gray-800">
        Order Processing
      </Link>
      {authed && (
        <div className="flex items-center gap-4 text-sm">
          <Link to="/" className="text-gray-600 hover:text-gray-900">
            Dashboard
          </Link>
          <Link to="/orders" className="text-gray-600 hover:text-gray-900">
            Orders
          </Link>
          <Link to="/upload" className="text-gray-600 hover:text-gray-900">
            Upload
          </Link>
          <button
            onClick={() => {
              clearToken();
              window.location.href = "/login";
            }}
            className="text-gray-500 hover:text-gray-800"
          >
            Sign out
          </button>
        </div>
      )}
    </nav>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NavBar />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders"
            element={
              <ProtectedRoute>
                <OrdersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders/:id"
            element={
              <ProtectedRoute>
                <OrderDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <UploadPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
