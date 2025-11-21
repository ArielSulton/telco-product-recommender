import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useToast } from '../context/ToastContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import LoadingSpinner from '../components/LoadingSpinner'
import useEventTracking from '../hooks/useEventTracking'
import recommendationService from '../services/recommendationService'

const ProductDetailPage = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { trackSubscribe } = useEventTracking()

  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [purchasing, setPurchasing] = useState(false)

  const loadProduct = useCallback(async () => {
    try {
      setLoading(true)
      // Use real API
      const productData = await recommendationService.getProduct(id)
      setProduct(productData)
    } catch (error) {
      console.error('Failed to load product:', error)
      setProduct(null)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadProduct()
  }, [loadProduct])

  const handlePurchase = async () => {
    if (!product) return

    setPurchasing(true)

    try {
      // Track subscribe event
      await trackSubscribe(product.product_id, null, {
        price: product.price,
        source: 'product_detail',
      })

      // Simulate purchase API call
      await new Promise((resolve) => setTimeout(resolve, 1500))

      // Show success message and redirect
      toast.success('Purchase successful! Package will be activated shortly.')
      navigate('/dashboard')
    } catch (error) {
      console.error('Purchase failed:', error)
      toast.error('Purchase failed. Please try again.')
    } finally {
      setPurchasing(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-cyan-50">
        <Navbar />
        <main className="flex-1 flex items-center justify-center">
          <LoadingSpinner size="lg" text="Loading product details..." />
        </main>
        <Footer />
      </div>
    )
  }

  if (!product) {
    return (
      <div className="min-h-screen flex flex-col bg-cyan-50">
        <Navbar />
        <main className="flex-1 container mx-auto px-4 py-12">
          <div className="card text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              Product Not Found
            </h2>
            <p className="text-gray-600 mb-6">
              The product you&apos;re looking for doesn&apos;t exist.
            </p>
            <button onClick={() => navigate('/products')} className="btn-primary">
              Back to Products
            </button>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  const formatData = (mb) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(0)} GB`
    }
    return `${mb} MB`
  }

  // Calculate streaming and sosmed data (example split)
  const internetQuota = product.quota_data_mb
  const streamingQuota = Math.floor(internetQuota * 0.2) // 20% for streaming
  const sosmedQuota = Math.floor(internetQuota * 0.1) // 10% for sosmed

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-12">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-8 text-center">
          DETAIL PRODUCT
        </h1>

        {/* Product Details Card */}
        <div className="max-w-3xl mx-auto">
          <div className="card border-2 border-cyan-400 mb-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
              Detail Paket
            </h2>

            <div className="space-y-4">
              <div className="flex justify-between items-center py-3 border-b border-gray-200">
                <span className="text-lg font-semibold text-gray-900">
                  Internet
                </span>
                <span className="text-xl font-bold text-green-700">
                  {formatData(internetQuota)}
                </span>
              </div>

              <div className="flex justify-between items-center py-3 border-b border-gray-200">
                <span className="text-lg font-semibold text-gray-900">
                  Streaming
                </span>
                <span className="text-xl font-bold text-green-700">
                  {formatData(streamingQuota)}
                </span>
              </div>

              <div className="flex justify-between items-center py-3 border-b border-gray-200">
                <span className="text-lg font-semibold text-gray-900">
                  Masa Aktif
                </span>
                <span className="text-xl font-bold text-green-700">
                  {product.validity_days} Hari
                </span>
              </div>
            </div>
          </div>

          {/* Purchase Card */}
          <div className="card border-2 border-cyan-400">
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Price:</p>
                <p className="text-3xl font-bold text-gray-900">
                  Rp {product.price.toLocaleString('id-ID')}
                </p>
              </div>

              <button
                onClick={handlePurchase}
                disabled={purchasing}
                className="btn-secondary px-12 py-4 text-lg disabled:opacity-50"
              >
                {purchasing ? 'Processing...' : 'Beli'}
              </button>
            </div>
          </div>

          {/* Additional Info */}
          {product.tags && product.tags.length > 0 && (
            <div className="mt-6 text-center">
              <div className="flex flex-wrap justify-center gap-2">
                {product.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 bg-cyan-100 text-cyan-800 text-sm rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Back Button */}
          <div className="mt-8 text-center">
            <button
              onClick={() => navigate(-1)}
              className="text-gray-700 hover:text-green-700 font-semibold"
            >
              ← Back to Products
            </button>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}

export default ProductDetailPage
