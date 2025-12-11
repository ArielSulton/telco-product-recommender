import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import EmptyState from '../components/EmptyState'
import { ShoppingBag, Calendar, Database, DollarSign, CheckCircle, TrendingUp, FileText, XCircle } from 'lucide-react'
import api from '../services/api'

const PurchaseHistoryPage = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [purchases, setPurchases] = useState([])
  const [totalPurchases, setTotalPurchases] = useState(0)
  const [totalSpent, setTotalSpent] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchPurchaseHistory()
  }, [])

  const fetchPurchaseHistory = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await api.get('/purchases/history?limit=50')
      setPurchases(response.data.purchases || [])
      setTotalPurchases(response.data.total_purchases || 0)
      setTotalSpent(response.data.total_spent || 0)
    } catch (err) {
      console.error('Failed to fetch purchase history:', err)
      setError('Gagal memuat riwayat pembelian. Silakan coba lagi.')
    } finally {
      setLoading(false)
    }
  }

  const formatPrice = (price) => {
    return new Intl.NumberFormat('id-ID').format(price)
  }

  const formatData = (mb) => {
    if (!mb) return 'N/A'
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`
    }
    return `${mb} MB`
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return new Intl.DateTimeFormat('id-ID', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date)
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-cyan-50 via-blue-50 to-purple-50">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8 animate-fade-in">
          <h1 className="text-4xl font-bold gradient-text mb-2 flex items-center gap-3">
            <FileText className="w-9 h-9" />
            Riwayat Pembelian
          </h1>
          <p className="text-gray-600">Lihat semua paket yang pernah Anda beli</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 animate-slide-up">
          {/* Total Purchases */}
          <div className="card bg-gradient-to-r from-blue-100 to-cyan-100 border-2 border-blue-300 hover-lift">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-600 rounded-full">
                <ShoppingBag className="w-8 h-8 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Total Pembelian</h3>
                <p className="text-3xl font-bold text-gray-900">{totalPurchases}</p>
              </div>
            </div>
          </div>

          {/* Total Spent */}
          <div className="card bg-gradient-to-r from-green-100 to-emerald-100 border-2 border-green-300 hover-lift">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-600 rounded-full">
                <DollarSign className="w-8 h-8 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Total Pengeluaran</h3>
                <p className="text-2xl font-bold text-gray-900">Rp {formatPrice(totalSpent)}</p>
              </div>
            </div>
          </div>

          {/* Average Purchase */}
          <div className="card bg-gradient-to-r from-purple-100 to-pink-100 border-2 border-purple-300 hover-lift">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-600 rounded-full">
                <TrendingUp className="w-8 h-8 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Rata-rata</h3>
                <p className="text-2xl font-bold text-gray-900">
                  Rp {totalPurchases > 0 ? formatPrice(Math.floor(totalSpent / totalPurchases)) : '0'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Purchase List */}
        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="card animate-pulse">
                <div className="flex gap-4">
                  <div className="w-20 h-20 bg-gray-200 rounded-lg"></div>
                  <div className="flex-1 space-y-3">
                    <div className="h-5 bg-gray-200 rounded w-1/2"></div>
                    <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                    <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                  </div>
                  <div className="h-6 bg-gray-200 rounded w-20"></div>
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="card text-center py-12 bg-red-50 border-2 border-red-200">
            <div className="flex items-center justify-center gap-2 text-red-600 font-semibold mb-4">
              <XCircle className="w-6 h-6" />
              <p>{error}</p>
            </div>
            <button
              onClick={fetchPurchaseHistory}
              className="btn-primary"
            >
              Coba Lagi
            </button>
          </div>
        ) : purchases.length === 0 ? (
          <div className="card animate-fade-in">
            <EmptyState
              type="purchases"
              action={() => navigate('/dashboard')}
              actionLabel="Lihat Rekomendasi"
            />
          </div>
        ) : (
          <div className="space-y-4 animate-slide-up">
            {purchases.map((purchase, index) => (
              <div
                key={purchase.purchase_id}
                className="card hover-lift border-2 border-transparent hover:border-green-300 transition-all"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  {/* Left: Product Info */}
                  <div className="flex-1">
                    <div className="flex items-start gap-3 mb-3">
                      <div className="p-2 bg-green-100 rounded-lg">
                        <CheckCircle className="w-6 h-6 text-green-600" />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-gray-900 mb-1">
                          {purchase.product_name}
                        </h3>
                        <p className="text-sm text-gray-500">
                          ID: {purchase.product_id}
                        </p>
                      </div>
                    </div>

                    {/* Product Details */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                      {purchase.quota_data_mb && (
                        <div className="flex items-center gap-2">
                          <Database className="w-4 h-4 text-cyan-600" />
                          <span className="text-gray-600">Kuota:</span>
                          <span className="font-semibold text-gray-900">
                            {formatData(purchase.quota_data_mb)}
                          </span>
                        </div>
                      )}

                      {purchase.validity_days && (
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-purple-600" />
                          <span className="text-gray-600">Masa Aktif:</span>
                          <span className="font-semibold text-gray-900">
                            {purchase.validity_days} Hari
                          </span>
                        </div>
                      )}

                      <div className="flex items-center gap-2">
                        <DollarSign className="w-4 h-4 text-green-600" />
                        <span className="text-gray-600">Harga:</span>
                        <span className="font-bold text-green-700">
                          Rp {formatPrice(purchase.price)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Purchase Info */}
                  <div className="text-left md:text-right border-t md:border-t-0 md:border-l border-gray-200 pt-4 md:pt-0 md:pl-6">
                    <div className="mb-2">
                      <p className="text-xs text-gray-500 mb-1">Tanggal Pembelian</p>
                      <p className="text-sm font-semibold text-gray-900">
                        {formatDate(purchase.purchase_date)}
                      </p>
                    </div>

                    <div className="mb-2">
                      <p className="text-xs text-gray-500 mb-1">Metode Pembayaran</p>
                      <p className="text-sm font-semibold text-gray-900 capitalize">
                        {purchase.payment_method}
                      </p>
                    </div>

                    <div className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-semibold">
                      <CheckCircle className="w-3 h-3" />
                      {purchase.status}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <Footer />
    </div>
  )
}

export default PurchaseHistoryPage
