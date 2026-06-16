import React, { useState, useEffect, useCallback } from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import ProductCard from '../components/ProductCard'
import LoadingSpinner from '../components/LoadingSpinner'
import CheckoutModal from '../components/CheckoutModal'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import recommendationService from '../services/recommendationService'

const categoryLabels = {
  starter: 'Paket Pemula',
  data: 'Paket Kuota Besar',
  voice: 'Paket Telepon',
  combo: 'Paket Keluarga/Kombo',
  retention: 'Paket Retensi',
  premium: 'Paket Data Premium',
}

const categoryOrder = ['starter', 'data', 'voice', 'combo', 'retention', 'premium']

const getProductCategory = (product) =>
  product.kategori_rekomendasi || product.product_family

const getCategoryLabel = (category) =>
  category === 'all' ? 'Semua Paket' : categoryLabels[category] || category

const ProductsPage = () => {
  const { user, refreshUser } = useAuth()
  const toast = useToast()
  const [products, setProducts] = useState([])
  const [filteredProducts, setFilteredProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState('all')

  // Single checkout modal state (lifted from ProductCard)
  const [checkoutProduct, setCheckoutProduct] = useState(null)
  const [showCheckout, setShowCheckout] = useState(false)

  const filterProducts = useCallback(() => {
    if (selectedCategory === 'all') {
      setFilteredProducts(products)
    } else {
      setFilteredProducts(
        products.filter((p) => getProductCategory(p) === selectedCategory)
      )
    }
  }, [selectedCategory, products])

  useEffect(() => {
    loadProducts()
  }, [])

  useEffect(() => {
    filterProducts()
  }, [filterProducts])

  const loadProducts = async () => {
    try {
      setLoading(true)
      // Use real API
      const data = await recommendationService.getProducts()
      setProducts(data.products || [])
    } catch (error) {
      console.error('Failed to load products:', error)
      // Fallback to empty array on error
      setProducts([])
    } finally {
      setLoading(false)
    }
  }

  const availableCategories = [
    ...new Set(products.map(getProductCategory).filter(Boolean)),
  ]
  const productCategories = [
    'all',
    ...categoryOrder.filter((category) => availableCategories.includes(category)),
    ...availableCategories.filter((category) => !categoryOrder.includes(category)),
  ]

  // Handlers for checkout modal
  const handleOpenCheckout = (product) => {
    setCheckoutProduct(product)
    setShowCheckout(true)
  }

  const handleCloseCheckout = () => {
    setShowCheckout(false)
    setCheckoutProduct(null)
  }

  const handleCheckoutSuccess = async (purchaseData) => {
    // Refresh user data to update balance
    if (refreshUser) {
      await refreshUser()
    }
    // Show success message
    toast.success(purchaseData.message || 'Pembelian berhasil! Paket sudah aktif.')
    // Close the modal
    handleCloseCheckout()
    // Reload products to reflect any changes
    loadProducts()
  }

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
            htmlFor="category-filter"
            className="block text-sm font-semibold text-gray-700 mb-2"
          >
            Filter Kategori Rekomendasi
          </label>
          <select
            id="category-filter"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="input-field max-w-md"
          >
            {productCategories.map((category) => (
              <option key={category} value={category}>
                {getCategoryLabel(category)}
              </option>
            ))}
          </select>
        </div>

        {/* Products by recommendation category */}
        {productCategories
          .filter((category) => category !== 'all')
          .map((category) => {
            const categoryProducts =
              selectedCategory === 'all'
                ? products.filter((p) => getProductCategory(p) === category)
                : selectedCategory === category
                ? filteredProducts
                : []

            if (categoryProducts.length === 0) return null

            return (
              <section key={category} className="mb-12">
                <h2 className="section-title">{getCategoryLabel(category)}</h2>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {categoryProducts.map((product) => (
                    <ProductCard
                      key={product.product_id}
                      product={product}
                      showReason={false}
                      onBuyClick={handleOpenCheckout}
                    />
                  ))}
                </div>
              </section>
            )
          })}

        {filteredProducts.length === 0 && (
          <div className="card text-center py-12">
            <p className="text-gray-600 text-lg">
              Tidak ada produk untuk kategori yang dipilih.
            </p>
          </div>
        )}
      </main>

      <Footer />

      {/* Single Checkout Modal - prevents flickering from multiple instances */}
      <CheckoutModal
        isOpen={showCheckout}
        onClose={handleCloseCheckout}
        product={checkoutProduct}
        userBalance={user?.balance || 0}
        onSuccess={handleCheckoutSuccess}
      />
    </div>
  )
}

export default ProductsPage
