import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import useEventTracking from '../hooks/useEventTracking'
import CheckoutModal from './CheckoutModal'
import { Database, Calendar, DollarSign, Star, ArrowRight, Lightbulb, ShoppingCart } from 'lucide-react'

const ProductCard = ({ product, variant, showReason = false, onPurchaseSuccess }) => {
  const navigate = useNavigate()
  const { user, refreshUser } = useAuth()
  const toast = useToast()
  const { trackView, trackClick } = useEventTracking()
  const [showCheckout, setShowCheckout] = useState(false)

  // Track view on mount
  useEffect(() => {
    if (product?.product_id) {
      trackView(product.product_id, variant)
    }
  }, [product?.product_id, variant, trackView])

  const handleViewDetail = () => {
    trackClick(product.product_id, variant, {
      source: 'product_card',
      action: 'view_detail',
    })
    navigate(`/products/${product.product_id}`)
  }

  const handleBuyClick = () => {
    trackClick(product.product_id, variant, {
      source: 'product_card',
      action: 'buy_click',
    })
    setShowCheckout(true)
  }

  const handleCheckoutSuccess = async (purchaseData) => {
    // Track purchase event
    trackClick(product.product_id, variant, {
      source: 'product_card',
      action: 'purchase_completed',
      purchase_id: purchaseData.purchase_id
    })

    // Refresh user data to update balance
    if (refreshUser) {
      await refreshUser()
    }

    // Callback to parent component
    onPurchaseSuccess?.(purchaseData)

    // Show success message
    toast.success(purchaseData.message || 'Pembelian berhasil! Paket sudah aktif.')
  }

  const formatPrice = (price) => {
    return new Intl.NumberFormat('id-ID').format(price)
  }

  const formatData = (mb) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(0)} GB`
    }
    return `${mb} MB`
  }

  return (
    <div className="card hover-lift group border-2 border-transparent hover:border-cyan-300 transition-all duration-300">
      {/* Product Header */}
      <div className="mb-4 pb-4 border-b border-gray-200">
        <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-green-700 transition-colors">
          {product.product_name || product.product_family}
        </h3>
        {product.quota_data_mb && (
          <div className="flex items-center gap-2">
            <Database className="w-6 h-6 text-cyan-600" />
            <p className="text-3xl font-bold gradient-text">
              {formatData(product.quota_data_mb)}
            </p>
          </div>
        )}
      </div>

      {/* Product Details */}
      <div className="space-y-3 mb-4">
        {product.validity_days && (
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <span className="text-gray-600">Validity:</span>
            </div>
            <span className="font-semibold text-gray-900">
              {product.validity_days} Days
            </span>
          </div>
        )}

        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-gray-500" />
            <span className="text-gray-600">Price:</span>
          </div>
          <span className="font-bold text-green-700">
            Rp {formatPrice(product.price)}
          </span>
        </div>

        {product.score && (
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-yellow-500" />
              <span className="text-gray-600">Match Score:</span>
            </div>
            <span className="font-semibold text-green-700">
              {(product.score * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {/* Recommendation Reason */}
      {showReason && product.reason && (
        <div className="mb-4 p-3 bg-gradient-to-r from-cyan-50 to-green-50 rounded-lg border border-cyan-200">
          <div className="flex items-start gap-2">
            <Lightbulb className="w-4 h-4 text-cyan-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-700 italic">
              {product.reason}
            </p>
          </div>
        </div>
      )}

      {/* CTA Buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleBuyClick}
          className="flex-1 bg-gradient-to-r from-green-600 to-emerald-600 text-white px-4 py-2.5 rounded-lg font-semibold hover:shadow-lg transition-all active-press inline-flex items-center justify-center gap-2"
          aria-label={`Buy ${product.product_name}`}
        >
          <ShoppingCart className="w-4 h-4" />
          Beli
        </button>

        <button
          onClick={handleViewDetail}
          className="flex-1 btn-primary text-base inline-flex items-center justify-center gap-2 active-press"
          aria-label={`View details for ${product.product_name}`}
        >
          Detail
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </button>
      </div>

      {/* Checkout Modal */}
      <CheckoutModal
        isOpen={showCheckout}
        onClose={() => setShowCheckout(false)}
        product={product}
        userBalance={user?.balance || 0}
        onSuccess={handleCheckoutSuccess}
      />

      {/* A/B Test Variant Indicator (development only) */}
      {variant && process.env.NODE_ENV === 'development' && (
        <div className="mt-2 text-xs text-gray-400 text-center">
          Variant: {variant}
        </div>
      )}
    </div>
  )
}

export default ProductCard
