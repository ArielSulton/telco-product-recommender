import React, { useState, useEffect, useCallback } from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import ProductCard from '../components/ProductCard'
import LoadingSpinner from '../components/LoadingSpinner'
import recommendationService from '../services/recommendationService'

const ProductsPage = () => {
  const [products, setProducts] = useState([])
  const [filteredProducts, setFilteredProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedFamily, setSelectedFamily] = useState('all')

  const filterProducts = useCallback(() => {
    if (selectedFamily === 'all') {
      setFilteredProducts(products)
    } else {
      setFilteredProducts(
        products.filter((p) => p.product_family === selectedFamily)
      )
    }
  }, [selectedFamily, products])

  useEffect(() => {
    loadProducts()
  }, [])

  useEffect(() => {
    filterProducts()
  }, [filterProducts])

  const loadProducts = async () => {
    try {
      setLoading(true)
      // Use mock data for development
      const data = recommendationService.mockProducts()
      setProducts(data.products || [])
    } catch (error) {
      console.error('Failed to load products:', error)
    } finally {
      setLoading(false)
    }
  }

  const productFamilies = ['all', ...new Set(products.map((p) => p.product_family))]

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-cyan-50">
        <Navbar />
        <main className="flex-1 flex items-center justify-center">
          <LoadingSpinner size="lg" text="Loading products..." />
        </main>
        <Footer />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-8">
        {/* Filter Section */}
        <div className="mb-8">
          <label
            htmlFor="family-filter"
            className="block text-sm font-semibold text-gray-700 mb-2"
          >
            Filter by Package Family
          </label>
          <select
            id="family-filter"
            value={selectedFamily}
            onChange={(e) => setSelectedFamily(e.target.value)}
            className="input-field max-w-md"
          >
            {productFamilies.map((family) => (
              <option key={family} value={family}>
                {family === 'all' ? 'All Products' : family}
              </option>
            ))}
          </select>
        </div>

        {/* Products by Family */}
        {productFamilies
          .filter((f) => f !== 'all')
          .map((family) => {
            const familyProducts =
              selectedFamily === 'all'
                ? products.filter((p) => p.product_family === family)
                : selectedFamily === family
                ? filteredProducts
                : []

            if (familyProducts.length === 0) return null

            return (
              <section key={family} className="mb-12">
                <h2 className="section-title">{family}</h2>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {familyProducts.map((product) => (
                    <ProductCard
                      key={product.product_id}
                      product={product}
                      showReason={false}
                    />
                  ))}
                </div>
              </section>
            )
          })}

        {filteredProducts.length === 0 && (
          <div className="card text-center py-12">
            <p className="text-gray-600 text-lg">
              No products found for the selected filter.
            </p>
          </div>
        )}
      </main>

      <Footer />
    </div>
  )
}

export default ProductsPage
