import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import ProductCard from '../components/ProductCard'
import recommendationService from '../services/recommendationService'
import { ArrowRight, Zap, Shield, TrendingUp } from 'lucide-react'

const HomePage = () => {
  // Fetch products for guest homepage
  const [featuredProducts, setFeaturedProducts] = useState([])

  useEffect(() => {
    const loadFeaturedProducts = async () => {
      try {
        const data = await recommendationService.getProducts({ limit: 4 })
        setFeaturedProducts(data.products || [])
      } catch (error) {
        console.error('Failed to load featured products:', error)
        setFeaturedProducts([])
      }
    }
    loadFeaturedProducts()
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="container mx-auto px-4 py-20 text-center animate-fade-in">
          <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6 animate-slide-up">
            WELCOME TO <span className="gradient-text">PAKETIFY</span>
          </h1>
          <p className="text-xl md:text-2xl text-gray-700 mb-10 max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '0.1s' }}>
            Find the Right Telco Product for You!
          </p>
          <Link to="/products" className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4 active-press animate-scale-in" style={{ animationDelay: '0.2s' }}>
            Get Started
            <ArrowRight className="w-5 h-5" />
          </Link>
        </section>

        {/* Features Section */}
        <section className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
            <div className="card text-center hover-lift animate-slide-up" style={{ animationDelay: '0.1s' }}>
              <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-cyan-400 to-cyan-600 rounded-full mb-4">
                <Zap className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Fast & Easy</h3>
              <p className="text-gray-600">Find your perfect plan in seconds with our smart recommendation system</p>
            </div>

            <div className="card text-center hover-lift animate-slide-up" style={{ animationDelay: '0.2s' }}>
              <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-green-400 to-green-600 rounded-full mb-4">
                <Shield className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Trusted & Secure</h3>
              <p className="text-gray-600">Your data is safe with our advanced security protocols</p>
            </div>

            <div className="card text-center hover-lift animate-slide-up" style={{ animationDelay: '0.3s' }}>
              <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-purple-400 to-purple-600 rounded-full mb-4">
                <TrendingUp className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Best Value</h3>
              <p className="text-gray-600">Get the most value for your money with tailored recommendations</p>
            </div>
          </div>
        </section>

        {/* Products Preview Section */}
        <section className="container mx-auto px-4 py-12">
          <h2 className="section-title text-center mb-8">Our Product</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {featuredProducts.map((product, index) => (
              <div key={product.product_id} className="card hover-lift animate-scale-in" style={{ animationDelay: `${0.1 * (index + 1)}s` }}>
                <div className="mb-4">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    {product.product_family}
                  </h3>
                  <p className="text-3xl font-bold gradient-text">
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
                    <span className="font-bold text-green-700">
                      Rp {product.price.toLocaleString('id-ID')}
                    </span>
                  </div>
                </div>

                <Link
                  to={`/products/${product.product_id}`}
                  className="block text-center btn-primary w-full active-press"
                >
                  View Detail
                </Link>
              </div>
            ))}
          </div>

          <div className="text-center mt-8">
            <Link to="/products" className="btn-primary inline-flex items-center gap-2 active-press">
              View All Products
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </section>

        {/* CTA Section */}
        <section className="bg-gradient-to-r from-green-600 to-cyan-400 py-20 mt-12">
          <div className="container mx-auto px-4 text-center">
            <h2 className="text-4xl font-bold text-white mb-4 animate-slide-up">
              Ready to Find Your Perfect Package?
            </h2>
            <p className="text-xl text-white mb-8 max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '0.1s' }}>
              Sign in to get personalized recommendations based on your usage patterns
            </p>
            <Link to="/login" className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4 active-press animate-scale-in" style={{ animationDelay: '0.2s' }}>
              Sign In Now
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default HomePage
