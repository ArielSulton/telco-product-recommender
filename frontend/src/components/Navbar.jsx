import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const Navbar = () => {
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-white shadow-md sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex justify-between items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-2">
            <div className="w-10 h-10 bg-gradient-to-br from-green-600 to-cyan-400 rounded-full flex items-center justify-center">
              <span className="text-white font-bold text-xl">P</span>
            </div>
            <span className="text-xl font-bold text-gray-900">PAKETIFY</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            <Link to="/" className="navbar-link">
              HOME
            </Link>
            <Link to="/about" className="navbar-link">
              ABOUT
            </Link>
            <Link to="/products" className="navbar-link">
              PRODUCTS
            </Link>

            {isAuthenticated ? (
              <>
                <Link to="/dashboard" className="navbar-link">
                  DASHBOARD
                </Link>
                <Link to="/purchases" className="navbar-link">
                  RIWAYAT
                </Link>
                {user?.role === 'admin' && (
                  <Link to="/admin" className="navbar-link text-green-700">
                    ADMIN
                  </Link>
                )}
                <button onClick={handleLogout} className="navbar-link">
                  LOGOUT
                </button>
                <Link
                  to="/profile"
                  className="flex items-center space-x-2 bg-cyan-100 px-4 py-2 rounded-full hover:bg-cyan-200 transition-colors"
                >
                  <div className="w-8 h-8 bg-gradient-to-br from-green-600 to-cyan-400 rounded-full flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-white"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                  <span className="text-sm font-semibold text-gray-700">
                    {user?.name || user?.phone}
                  </span>
                </Link>
              </>
            ) : (
              <Link to="/login" className="navbar-link font-bold">
                LOGIN
              </Link>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              {mobileMenuOpen ? (
                <path d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-4 pb-4 space-y-4">
            <Link
              to="/"
              className="block navbar-link"
              onClick={() => setMobileMenuOpen(false)}
            >
              HOME
            </Link>
            <Link
              to="/about"
              className="block navbar-link"
              onClick={() => setMobileMenuOpen(false)}
            >
              ABOUT
            </Link>
            <Link
              to="/products"
              className="block navbar-link"
              onClick={() => setMobileMenuOpen(false)}
            >
              PRODUCTS
            </Link>

            {isAuthenticated ? (
              <>
                <Link
                  to="/dashboard"
                  className="block navbar-link"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  DASHBOARD
                </Link>
                <Link
                  to="/purchases"
                  className="block navbar-link"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  RIWAYAT
                </Link>
                {user?.role === 'admin' && (
                  <Link
                    to="/admin"
                    className="block navbar-link text-green-700"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    ADMIN
                  </Link>
                )}
                <Link
                  to="/profile"
                  className="block navbar-link"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  PROFILE
                </Link>
                <button
                  onClick={() => {
                    handleLogout()
                    setMobileMenuOpen(false)
                  }}
                  className="block w-full text-left navbar-link"
                >
                  LOGOUT
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className="block navbar-link font-bold"
                onClick={() => setMobileMenuOpen(false)}
              >
                LOGIN
              </Link>
            )}
          </div>
        )}
      </div>
    </nav>
  )
}

export default Navbar
