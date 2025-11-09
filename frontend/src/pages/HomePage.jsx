import React from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import ProductCard from '../components/ProductCard'
import recommendationService from '../services/recommendationService'

const HomePage = () => {
  // Use mock data for guest homepage
  const mockProducts = recommendationService.mockProducts().products.slice(0, 4)

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="container mx-auto px-4 py-16 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            WELCOME TO <span className="text-green-700">PAKETIFY</span>
          </h1>
          <p className="text-xl md:text-2xl text-gray-700 mb-8">
            Find the Right Telco Product for You!
          </p>
          <Link to="/products" className="btn-primary inline-block">
            Get Started
          </Link>
        </section>

        {/* Products Preview Section */}
        <section className="container mx-auto px-4 py-12">
          <h2 className="section-title">Our Product</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {mockProducts.map((product) => (
              <div key={product.product_id} className="card">
                <div className="mb-4">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    {product.product_family}
                  </h3>
                  <p className="text-3xl font-bold text-green-700">
                    {(product.quota_data_mb / 1024).toFixed(0)} GB
                  </p>
                </div>

                <div className="space-y-2 mb-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Validity:</span>
                    <span className="font-semibold">
                      {product.validity_days} Days
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Price:</span>
                    <span className="font-bold">
                      Rp {product.price.toLocaleString('id-ID')}
                    </span>
                  </div>
                </div>

                <Link
                  to={`/products/${product.product_id}`}
                  className="block text-center btn-primary w-full"
                >
                  View Detail
                </Link>
              </div>
            ))}
          </div>

          <div className="text-center mt-8">
            <Link to="/products" className="btn-secondary">
              View All Products
            </Link>
          </div>
        </section>

        {/* CTA Section */}
        <section className="bg-gradient-to-r from-cyan-100 to-cyan-200 py-16 mt-12">
          <div className="container mx-auto px-4 text-center">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Ready to Find Your Perfect Package?
            </h2>
            <p className="text-lg text-gray-700 mb-6">
              Sign in to get personalized recommendations based on your usage patterns
            </p>
            <Link to="/login" className="btn-primary inline-block">
              Sign In Now
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default HomePage
