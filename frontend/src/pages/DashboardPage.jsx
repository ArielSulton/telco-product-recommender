import React from 'react'
import { useAuth } from '../context/AuthContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import RecommendationWidget from '../components/RecommendationWidget'
import ProductCard from '../components/ProductCard'

const DashboardPage = () => {
  const { user } = useAuth()

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

      <main className="flex-1 container mx-auto px-4 py-8">
        {/* User Info Card */}
        <div className="card mb-8 bg-gradient-to-r from-cyan-100 to-cyan-200">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="text-center md:text-left">
              <h2 className="text-lg font-semibold text-gray-700 mb-1">Nomor</h2>
              <p className="text-2xl font-bold text-gray-900">{userData.phone}</p>
            </div>
            <div className="w-px h-16 bg-cyan-400 hidden md:block"></div>
            <div className="text-center md:text-right">
              <h2 className="text-lg font-semibold text-gray-700 mb-1">Pulsa</h2>
              <p className="text-2xl font-bold text-gray-900">
                Rp {userData.balance.toLocaleString('id-ID')}
              </p>
            </div>
          </div>
        </div>

        {/* Data Usage Card */}
        <div className="card mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
            Data Usage
          </h2>

          <div className="space-y-4">
            <div className="flex justify-between items-center py-2">
              <span className="text-lg font-semibold text-gray-900">
                Sisa Internet
              </span>
              <span className="text-xl font-bold text-green-700">
                {userData.dataUsage.internet} GB
              </span>
            </div>

            <div className="flex justify-between items-center py-2">
              <span className="text-lg font-semibold text-gray-900">
                Sisa Streaming
              </span>
              <span className="text-xl font-bold text-green-700">
                {userData.dataUsage.streaming} GB
              </span>
            </div>

            <div className="flex justify-between items-center py-2">
              <span className="text-lg font-semibold text-gray-900">
                Sisa Sosmed
              </span>
              <span className="text-xl font-bold text-green-700">
                {userData.dataUsage.sosmed} MB
              </span>
            </div>

            <div className="flex justify-between items-center py-2">
              <span className="text-lg font-semibold text-gray-900">
                Sisa Telpon
              </span>
              <span className="text-xl font-bold text-green-700">
                {userData.dataUsage.voice} Menit
              </span>
            </div>
          </div>
        </div>

        {/* Personalized Recommendations */}
        <RecommendationWidget
          title="Recommended"
          limit={3}
          useMock={true}
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
    </div>
  )
}

export default DashboardPage
