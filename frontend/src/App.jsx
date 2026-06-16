import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { RecommendationProvider } from './context/RecommendationContext'
import { ToastProvider } from './context/ToastContext'

// Pages
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import AdminDashboardPage from './pages/AdminDashboardPage'
import ProductsPage from './pages/ProductsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import ProfilePage from './pages/ProfilePage'
import PurchaseHistoryPage from './pages/PurchaseHistoryPage'
import AboutPage from './pages/AboutPage'
import NotFoundPage from './pages/NotFoundPage'

// Components
import ErrorBoundary from './components/ErrorBoundary'
import LoadingSpinner from './components/LoadingSpinner'

// ✅ Protected Route Component using AuthContext
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />
}

// ✅ Admin Protected Route Component
const AdminProtectedRoute = ({ children }) => {
  const { user, isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  return children
}

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <ToastProvider>
          <AuthProvider>
            <RecommendationProvider>
              <Routes>
              {/* Public Routes */}
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/products" element={<ProductsPage />} />
              <Route path="/products/:id" element={<ProductDetailPage />} />

              {/* Protected Routes */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <DashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <ProfilePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/purchases"
                element={
                  <ProtectedRoute>
                    <PurchaseHistoryPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin"
                element={
                  <AdminProtectedRoute>
                    <AdminDashboardPage />
                  </AdminProtectedRoute>
                }
              />

              {/* 404 */}
              <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </RecommendationProvider>
          </AuthProvider>
        </ToastProvider>
      </Router>
    </ErrorBoundary>
  )
}

export default App
