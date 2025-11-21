import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import RecommendationWidget from '../components/RecommendationWidget'
import ProductCard from '../components/ProductCard'
import QuestionnaireModal from '../components/QuestionnaireModal'
import { Smartphone, Wallet, Wifi, Video, MessageCircle, Phone } from 'lucide-react'
import api from '../services/api'

const DashboardPage = () => {
  const { user } = useAuth()
  const [showQuestionnaire, setShowQuestionnaire] = useState(false)
  const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false)
  const [segment, setSegment] = useState(null)

  // Check onboarding status and fetch segment on mount
  useEffect(() => {
    const checkOnboardingStatus = async () => {
      if (hasCheckedOnboarding) return

      try {
        const response = await api.get('/api/v1/users/me')
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
    }
  }, [user, hasCheckedOnboarding])

  const handleQuestionnaireComplete = () => {
    setShowQuestionnaire(false)
    // Optionally refresh recommendations here
  }

  // Mock user data and recent transactions
  const userData = {
    phone: user?.phone || '0812 3456 7890',
    balance: user?.balance || 100000,
    dataUsage: {
      internet: 6.7,
      streaming: 1.0,
      sosmed: 872,
      voice: 27,
    },
  }

  const recentTransactions = [
    {
      product_id: 'PKT001',
      product_name: 'Paket For You',
      quota_data_mb: 10240,
      validity_days: 7,
      price: 15000,
      purchase_date: '2024-11-01',
    },
  ]

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
                <p className="text-2xl font-bold text-gray-900">{userData.phone}</p>
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
                  Rp {userData.balance.toLocaleString('id-ID')}
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

        {/* Data Usage Card */}
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
                  {userData.dataUsage.internet} GB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(userData.dataUsage.internet / 10) * 100}%` }}
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
                  {userData.dataUsage.streaming} GB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(userData.dataUsage.streaming / 5) * 100}%` }}
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
                  {userData.dataUsage.sosmed} MB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(userData.dataUsage.sosmed / 1000) * 100}%` }}
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
                  {userData.dataUsage.voice} Menit
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="progress-bar h-3"
                  style={{ width: `${(userData.dataUsage.voice / 60) * 100}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Personalized Recommendations */}
        <RecommendationWidget
          title="Recommended"
          limit={3}
        />

        {/* Recent Transactions */}
        {recentTransactions.length > 0 && (
          <section className="mt-12">
            <h2 className="section-title">Recent Transaction</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {recentTransactions.map((transaction, index) => (
                <ProductCard
                  key={`${transaction.product_id}-${index}`}
                  product={transaction}
                  showReason={false}
                />
              ))}
            </div>
          </section>
        )}
      </main>

      <Footer />

      {/* Onboarding Questionnaire Modal */}
      <QuestionnaireModal
        isOpen={showQuestionnaire}
        onClose={() => setShowQuestionnaire(false)}
        onComplete={handleQuestionnaireComplete}
      />
    </div>
  )
}

export default DashboardPage
