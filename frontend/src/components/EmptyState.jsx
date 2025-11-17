import React from 'react'
import { Package, ShoppingCart, BarChart3, FileText, AlertCircle } from 'lucide-react'

/**
 * Reusable empty state component with illustrations
 *
 * Types: products, purchases, recommendations, analytics, generic
 */
const EmptyState = ({
  type = 'generic',
  title,
  description,
  action,
  actionLabel,
  icon: CustomIcon
}) => {
  // Predefined empty states
  const emptyStates = {
    products: {
      icon: Package,
      title: 'Belum Ada Produk',
      description: 'Belum ada produk yang tersedia saat ini. Silakan tambahkan produk baru atau sync dari database.',
      color: 'text-blue-500'
    },
    purchases: {
      icon: ShoppingCart,
      title: 'Belum Ada Pembelian',
      description: 'Anda belum melakukan pembelian paket apapun. Jelajahi paket yang tersedia dan temukan yang cocok untuk Anda!',
      color: 'text-green-500'
    },
    recommendations: {
      icon: BarChart3,
      title: 'Belum Ada Rekomendasi',
      description: 'Sistem sedang mempelajari preferensi Anda. Lengkapi profil dan lakukan beberapa aktivitas untuk mendapatkan rekomendasi personal.',
      color: 'text-purple-500'
    },
    analytics: {
      icon: FileText,
      title: 'Belum Ada Data',
      description: 'Belum ada data analitik yang tersedia. Data akan muncul setelah ada aktivitas pengguna.',
      color: 'text-cyan-500'
    },
    generic: {
      icon: AlertCircle,
      title: 'Tidak Ada Data',
      description: 'Belum ada data yang tersedia untuk ditampilkan.',
      color: 'text-gray-500'
    }
  }

  const state = emptyStates[type] || emptyStates.generic
  const Icon = CustomIcon || state.icon
  const displayTitle = title || state.title
  const displayDescription = description || state.description

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      {/* Icon/Illustration */}
      <div className={`mb-6 p-6 rounded-full bg-gray-50 ${state.color}`}>
        <Icon className="w-16 h-16" strokeWidth={1.5} />
      </div>

      {/* Title */}
      <h3 className="text-xl font-bold text-gray-900 mb-3">
        {displayTitle}
      </h3>

      {/* Description */}
      <p className="text-gray-600 max-w-md mb-6">
        {displayDescription}
      </p>

      {/* Action Button */}
      {action && actionLabel && (
        <button
          onClick={action}
          className="btn-primary px-6 py-2.5"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}

export default EmptyState
