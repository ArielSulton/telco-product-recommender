import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import RecommendationWidget from '../components/RecommendationWidget'
import ProductCard from '../components/ProductCard'
import CheckoutModal from '../components/CheckoutModal'
import QuestionnaireModal from '../components/QuestionnaireModal'
import { Smartphone, Wallet, Wifi, Video, MessageCircle, Phone, Package, Calendar, Database } from 'lucide-react'
import api from '../services/api'

const DashboardPage = () => {
  const { user, refreshUser } = useAuth()
  const toast = useToast()
  const [showQuestionnaire, setShowQuestionnaire] = useState(false)
  const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false)
  const [segment, setSegment] = useState(null)

  // Single checkout modal state
  const [checkoutProduct, setCheckoutProduct] = useState(null)
  const [showCheckout, setShowCheckout] = useState(false)

  // Recent transactions state
  const [recentTransactions, setRecentTransactions] = useState([])
  const [loadingTransactions, setLoadingTransactions] = useState(true)

  // Active packages state (last 3 purchased packages as "active")
  const [activePackages, setActivePackages] = useState([])
  const [loadingPackages, setLoadingPackages] = useState(true)

  // Key to force RecommendationWidget refresh
  const [recommendationKey, setRecommendationKey] = useState(0)

  // Fetch recent transactions
  const fetchRecentTransactions = async () => {
    try {
      setLoadingTransactions(true)
      const response = await api.get('/purchases/history?limit=3')
      setRecentTransactions(response.data.purchases || [])
    } catch (error) {
      console.error('Failed to fetch recent transactions:', error)
      setRecentTransactions([])
    } finally {
      setLoadingTransactions(false)
    }
  }

  // Fetch active packages (recent purchases that are still "active")
  const fetchActivePackages = async () => {
    try {
      setLoadingPackages(true)
      const response = await api.get('/purchases/history?limit=5')
      // Filter to show only recent packages (within validity period)
      const packages = response.data.purchases || []
      setActivePackages(packages.slice(0, 3)) // Show max 3 active packages
    } catch (error) {
      console.error('Failed to fetch active packages:', error)
      setActivePackages([])
    } finally {
      setLoadingPackages(false)
    }
  }

  // Check onboarding status and fetch segment on mount
  useEffect(() => {
    const checkOnboardingStatus = async () => {
      if (hasCheckedOnboarding) return

      try {
        const response = await api.get('/users/me')
        const hasCompletedOnboarding = response.data?.user?.has_completed_onboarding
        const userSegment = response.data?.user?.segment

        // Store segment info
        if (userSegment) {
          setSegment(userSegment)
        }

        // Show questionnaire if not completed
        if (!hasCompletedOnboarding) {
          // Small delay for better UX
          setTimeout(() => setShowQuestionnaire(true), 500)
        }

        setHasCheckedOnboarding(true)
      } catch (error) {
        console.error('Failed to check onboarding status:', error)
        setHasCheckedOnboarding(true)
      }
    }

    if (user) {
      checkOnboardingStatus()
      fetchRecentTransactions()
      fetchActivePackages()
    }
  }, [user, hasCheckedOnboarding])

  const handleQuestionnaireComplete = () => {
    setShowQuestionnaire(false)
    // Optionally refresh recommendations here
  }

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
    if (refreshUser) {
      await refreshUser()
    }
    // Refresh recent transactions and active packages
    await fetchRecentTransactions()
    await fetchActivePackages()
    // Trigger RecommendationWidget refresh by changing key
    setRecommendationKey(prev => prev + 1)
    toast.success(purchaseData.message || 'Pembelian berhasil! Paket sudah aktif.')
    handleCloseCheckout()
  }

  // Format phone number for display
  const formatPhone = (phone) => {
    if (!phone) return '-'
    // Format: 0812 3456 7890
    return phone.replace(/(\d{4})(\d{4})(\d+)/, '$1 $2 $3')
  }

  // Data usage is mock for demo (requires real telco tracking system)
  const mockDataUsage = {
    internet: 6.7,
    streaming: 1.0,
    sosmed: 872,
    voice: 27,
  }

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-8 animate-fade-in">
        {/* User Info Card */}
        <div className="card mb-8 bg-gradient-to-r from-cyan-100 to-cyan-200 hover-lift border-2 border-cyan-300">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="text-center md:text-left flex items-center gap-4">
              <div className="p-3 bg-cyan-600 rounded-full">
                <Smartphone className="w-8 h-8 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-700 mb-1">Nomor</h2>
                <p className="text-2xl font-bold text-gray-900">{formatPhone(user?.phone)}</p>
              </div>
            </div>
            <div className="w-px h-16 bg-cyan-400 hidden md:block"></div>
            <div className="text-center md:text-right flex items-center gap-4">
              <div className="p-3 bg-green-600 rounded-full">
                <Wallet className="w-8 h-8 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-700 mb-1">Pulsa</h2>
                <p className="text-2xl font-bold text-gray-900">
                  Rp {(user?.balance || 0).toLocaleString('id-ID')}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* User Segment Card */}
        {segment && (
          <div className={`card mb-8 hover-lift animate-slide-up bg-gradient-to-r from-${segment.color}-50 to-${segment.color}-100 border-2 border-${segment.color}-300`}>
            <div className="flex items-center gap-4">
              <div className="text-6xl">{segment.icon}</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-2xl font-bold text-gray-900">{segment.name}</h3>
                  <span className={`px-3 py-1 rounded-full text-sm font-semibold bg-${segment.color}-200 text-${segment.color}-800`}>
                    Segment ID: {segment.segment_id}
                  </span>
                </div>
                <p className="text-gray-700 text-lg">{segment.description}</p>
              </div>
            </div>
          </div>
        )}

        {/* Data Usage Card (Mock Data - requires real telco tracking) */}
        <div className="card mb-8 hover-lift animate-slide-up">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
            Data Usage
          </h2>

          <div className="space-y-6">
            {/* Internet */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <Wifi className="w-6 h-6 text-cyan-600" />
                  <span className="text-lg font-semibold text-gray-900">
                    Sisa Internet
                  </span>
                </div>
                <span className="text-xl font-bold text-green-700">
                  {mockDataUsage.internet} GB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(mockDataUsage.internet / 10) * 100}%` }}
                ></div>
              </div>
            </div>

            {/* Streaming */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <Video className="w-6 h-6 text-purple-600" />
                  <span className="text-lg font-semibold text-gray-900">
                    Sisa Streaming
                  </span>
                </div>
                <span className="text-xl font-bold text-green-700">
                  {mockDataUsage.streaming} GB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(mockDataUsage.streaming / 5) * 100}%` }}
                ></div>
              </div>
            </div>

            {/* Sosmed */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <MessageCircle className="w-6 h-6 text-pink-600" />
                  <span className="text-lg font-semibold text-gray-900">
                    Sisa Sosmed
                  </span>
                </div>
                <span className="text-xl font-bold text-green-700">
                  {mockDataUsage.sosmed} MB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(mockDataUsage.sosmed / 1000) * 100}%` }}
                ></div>
              </div>
            </div>

            {/* Telpon */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <Phone className="w-6 h-6 text-orange-600" />
                  <span className="text-lg font-semibold text-gray-900">
                    Sisa Telpon
                  </span>
                </div>
                <span className="text-xl font-bold text-green-700">
                  {mockDataUsage.voice} Menit
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(mockDataUsage.voice / 60) * 100}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Active Packages */}
        <div className="card mb-8 hover-lift animate-slide-up">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
            <Package className="w-7 h-7 inline-block mr-2 text-cyan-600" />
            Paket Aktif
          </h2>

          {loadingPackages ? (
            <div className="space-y-4">
              {Array.from({ length: 2 }).map((_, index) => (
                <div key={index} className="animate-pulse flex items-center gap-4 p-4 bg-gray-100 rounded-lg">
                  <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                    <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : activePackages.length > 0 ? (
            <div className="space-y-4">
              {activePackages.map((pkg, index) => (
                <div
                  key={pkg.purchase_id || index}
                  className="flex items-center gap-4 p-4 bg-gradient-to-r from-green-50 to-cyan-50 rounded-lg border-2 border-green-200"
                >
                  <div className="p-3 bg-green-600 rounded-full">
                    <Package className="w-6 h-6 text-white" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold text-gray-900">{pkg.product_name}</h3>
                    <div className="flex flex-wrap gap-4 text-sm text-gray-600 mt-1">
                      {pkg.quota_data_mb && (
                        <span className="flex items-center gap-1">
                          <Database className="w-4 h-4 text-cyan-600" />
                          {pkg.quota_data_mb >= 1024
                            ? `${(pkg.quota_data_mb / 1024).toFixed(1)} GB`
                            : `${pkg.quota_data_mb} MB`}
                        </span>
                      )}
                      {pkg.validity_days && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-4 h-4 text-purple-600" />
                          {pkg.validity_days} Hari
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-semibold">
                      Aktif
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Package className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">Belum ada paket aktif</p>
              <p className="text-sm text-gray-400 mt-1">Beli paket untuk mulai menggunakan layanan</p>
            </div>
          )}
        </div>

        {/* Personalized Recommendations */}
        <RecommendationWidget
          key={recommendationKey}
          title="Recommended"
          limit={3}
          onBuyClick={handleOpenCheckout}
        />

        {/* Recent Transactions */}
        <section className="mt-12">
          <h2 className="section-title">Recent Transaction</h2>

          {loadingTransactions ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="card animate-pulse">
                  <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
                  <div className="h-10 bg-gray-200 rounded w-full"></div>
                </div>
              ))}
            </div>
          ) : recentTransactions.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {recentTransactions.map((transaction, index) => (
                <ProductCard
                  key={transaction.purchase_id || `${transaction.product_id}-${index}`}
                  product={{
                    product_id: transaction.product_id,
                    product_name: transaction.product_name,
                    quota_data_mb: transaction.quota_data_mb,
                    validity_days: transaction.validity_days,
                    price: transaction.price,
                  }}
                  showReason={false}
                  onBuyClick={handleOpenCheckout}
                />
              ))}
            </div>
          ) : (
            <div className="card text-center py-8">
              <p className="text-gray-500">Belum ada transaksi. Mulai berlangganan paket sekarang!</p>
            </div>
          )}
        </section>
      </main>

      <Footer />

      {/* Onboarding Questionnaire Modal */}
      <QuestionnaireModal
        isOpen={showQuestionnaire}
        onClose={() => setShowQuestionnaire(false)}
        onComplete={handleQuestionnaireComplete}
      />

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

export default DashboardPage
