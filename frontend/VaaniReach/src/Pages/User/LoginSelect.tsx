import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, Lock, User as UserIcon, ArrowRight } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import { useApp } from '../../Context/AppContext'

export default function Login() {
  const navigate = useNavigate()
  const { setUserName } = useApp()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setUserName(name || email.split('@')[0] || 'Citizen')
    navigate('/user/circulars')
  }

  return (
    <PageShell showBack backTo="/role">
      <div className="pt-4 sm:pt-10 flex justify-center">
        <Card strong className="w-full max-w-md">
          <div className="flex rounded-full bg-blossom-50 p-1 mb-6">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 rounded-full py-2 text-sm font-medium transition-all ${
                  mode === m ? 'bg-white text-blossom-600 shadow-sm' : 'text-plum-800/60'
                }`}
              >
                {m === 'login' ? 'Log in' : 'Register'}
              </button>
            ))}
          </div>

          <h1 className="font-display text-2xl font-semibold text-plum-900">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="mt-1 text-sm text-plum-800/60">
            {mode === 'login' ? 'Log in to view circulars in your language.' : 'Just a few details to get you started.'}
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {mode === 'register' && (
              <div className="relative">
                <UserIcon size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-plum-800/40" />
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Full name"
                  className="w-full rounded-2xl border border-blossom-100 bg-white/80 py-3 pl-11 pr-4 text-sm outline-none focus:border-blossom-300 transition-colors"
                />
              </div>
            )}
            <div className="relative">
              <Mail size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-plum-800/40" />
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                className="w-full rounded-2xl border border-blossom-100 bg-white/80 py-3 pl-11 pr-4 text-sm outline-none focus:border-blossom-300 transition-colors"
              />
            </div>
            <div className="relative">
              <Lock size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-plum-800/40" />
              <input
                required
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full rounded-2xl border border-blossom-100 bg-white/80 py-3 pl-11 pr-4 text-sm outline-none focus:border-blossom-300 transition-colors"
              />
            </div>

            <Button type="submit" className="w-full mt-2" icon={<ArrowRight size={17} />}>
              {mode === 'login' ? 'Log in' : 'Create account'}
            </Button>
          </form>
        </Card>
      </div>
    </PageShell>
  )
}
