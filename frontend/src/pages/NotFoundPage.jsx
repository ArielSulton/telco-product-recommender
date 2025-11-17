import React from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

const NotFoundPage = () => {
  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="card max-w-2xl w-full text-center">
          <div className="text-9xl font-bold text-green-700 mb-4">404</div>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Page Not Found
          </h1>
          <p className="text-lg text-gray-600 mb-8">
            Oops! The page you&apos;re looking for doesn&apos;t exist. It might have been
            moved or deleted.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/" className="btn-primary">
              Go to Homepage
            </Link>
            <Link to="/products" className="btn-secondary">
              Browse Products
            </Link>
          </div>

          <div className="mt-12">
            <p className="text-sm text-gray-500">
              Need help? Contact our support team.
            </p>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}

export default NotFoundPage
