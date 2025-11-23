import React from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { Target, Zap, Shield, BarChart3 } from 'lucide-react'

const AboutPage = () => {
  const features = [
    {
      icon: Target,
      title: 'Personalized Recommendations',
      description:
        'Get product recommendations tailored to your usage patterns using advanced machine learning.',
    },
    {
      icon: Zap,
      title: 'Real-Time Insights',
      description:
        'Track your data usage and get instant recommendations based on your current needs.',
    },
    {
      icon: Shield,
      title: 'Secure & Private',
      description:
        'Your data is encrypted and secure. We prioritize your privacy in all recommendations.',
    },
    {
      icon: BarChart3,
      title: 'Smart Analytics',
      description:
        'Understand your usage patterns with detailed analytics and insights.',
    },
  ]

  const teamMembers = [
    { name: 'Team A25-CS007', role: 'Development Team' },
  ]

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="bg-gradient-to-r from-green-600 to-cyan-400 py-20">
          <div className="container mx-auto px-4 text-center text-white">
            <h1 className="text-4xl md:text-5xl font-bold mb-6">
              About Paketify
            </h1>
            <p className="text-xl md:text-2xl max-w-3xl mx-auto">
              Your intelligent telco package recommendation system powered by
              machine learning
            </p>
          </div>
        </section>

        {/* Mission Section */}
        <section className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <h2 className="section-title text-center">Our Mission</h2>
            <p className="text-lg text-gray-700 text-center mb-8">
              At Paketify, we believe that choosing the right telco package
              shouldn&apos;t be complicated. Our mission is to simplify your decision
              by providing personalized recommendations based on your actual
              usage patterns, preferences, and behavior.
            </p>
            <p className="text-lg text-gray-700 text-center">
              Using state-of-the-art machine learning algorithms including
              K-Means segmentation, LightFM collaborative filtering, and XGBoost
              ranking, we deliver recommendations that truly match your needs.
            </p>
          </div>
        </section>

        {/* Features Section */}
        <section className="bg-white py-16">
          <div className="container mx-auto px-4">
            <h2 className="section-title text-center">Key Features</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-6xl mx-auto">
              {features.map((feature, index) => {
                const IconComponent = feature.icon
                return (
                  <div key={index} className="card text-center">
                    <div className="flex justify-center mb-4">
                      <IconComponent className="w-12 h-12 text-green-600" />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 mb-3">
                      {feature.title}
                    </h3>
                    <p className="text-gray-600">{feature.description}</p>
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="container mx-auto px-4 py-16">
          <h2 className="section-title text-center">How It Works</h2>

          <div className="max-w-4xl mx-auto space-y-8">
            <div className="card">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-12 h-12 bg-green-700 text-white rounded-full flex items-center justify-center font-bold text-xl">
                  1
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    User Segmentation
                  </h3>
                  <p className="text-gray-600">
                    We analyze your usage patterns using K-Means clustering to
                    identify your user segment based on RFM (Recency, Frequency,
                    Monetary) metrics, ARPU, and usage behavior.
                  </p>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-12 h-12 bg-green-700 text-white rounded-full flex items-center justify-center font-bold text-xl">
                  2
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    Candidate Generation
                  </h3>
                  <p className="text-gray-600">
                    Using LightFM collaborative filtering and segment-based
                    popularity, we generate a pool of relevant product candidates
                    that match your profile.
                  </p>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-12 h-12 bg-green-700 text-white rounded-full flex items-center justify-center font-bold text-xl">
                  3
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    Intelligent Ranking
                  </h3>
                  <p className="text-gray-600">
                    Our XGBoost ranking model scores and ranks candidates based on
                    multiple features to predict which packages you&apos;re most likely
                    to prefer.
                  </p>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-12 h-12 bg-green-700 text-white rounded-full flex items-center justify-center font-bold text-xl">
                  4
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    Personalized Results
                  </h3>
                  <p className="text-gray-600">
                    We apply MMR diversification to ensure variety in
                    recommendations and provide SHAP-based explanations for
                    transparency.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Tech Stack */}
        <section className="bg-white py-16">
          <div className="container mx-auto px-4">
            <h2 className="section-title text-center">Technology Stack</h2>

            <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-3 gap-6">
              {[
                'React 18',
                'FastAPI',
                'PostgreSQL',
                'Redis',
                'scikit-learn',
                'LightFM',
                'XGBoost',
                'MLflow',
                'Apache Airflow',
                'Docker',
                'Tailwind CSS',
                'Prometheus',
              ].map((tech, index) => (
                <div
                  key={index}
                  className="card text-center hover:scale-105 transition-transform"
                >
                  <p className="font-semibold text-gray-900">{tech}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Team Section */}
        <section className="container mx-auto px-4 py-16">
          <h2 className="section-title text-center">Our Team</h2>

          <div className="max-w-2xl mx-auto">
            {teamMembers.map((member, index) => (
              <div key={index} className="card text-center">
                <div className="w-20 h-20 bg-gradient-to-br from-green-600 to-cyan-400 rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-white font-bold text-2xl">
                    {member.name.charAt(0)}
                  </span>
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-1">
                  {member.name}
                </h3>
                <p className="text-gray-600">{member.role}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA Section */}
        <section className="bg-gradient-to-r from-green-600 to-cyan-400 text-white py-16">
          <div className="container mx-auto px-4 text-center">
            <h2 className="text-3xl font-bold mb-4">Ready to Get Started?</h2>
            <p className="text-xl mb-8">
              Discover the perfect telco package for your needs today
            </p>
            <a href="/products" className="btn-primary inline-block">
              Explore Products
            </a>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default AboutPage
