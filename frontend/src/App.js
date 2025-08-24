import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import { Toaster, toast } from 'sonner';
import { Card } from './components/ui/card';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Badge } from './components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './components/ui/dialog';
import { Coins, Trophy, Clock, Users, Gift, TrendingUp, Crown, Star } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = React.createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUserInfo();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchUserInfo = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user info:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password });
      const { access_token, user: userData } = response.data;
      
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Login failed' 
      };
    }
  };

  const register = async (name, email, password) => {
    try {
      await axios.post(`${API}/auth/register`, { name, email, password });
      return await login(email, password);
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Registration failed' 
      };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  const updateUserCoins = (newCoins) => {
    setUser(prev => ({ ...prev, coins: newCoins }));
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      login, 
      register, 
      logout, 
      loading, 
      updateUserCoins,
      refreshUser: fetchUserInfo 
    }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// WebSocket Hook
const useWebSocket = (userId) => {
  const [socket, setSocket] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const { updateUserCoins } = useAuth();

  useEffect(() => {
    if (!userId) return;

    const wsUrl = `${BACKEND_URL.replace('http', 'ws')}/ws/${userId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setSocket(ws);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'balance_update') {
        const { coins, delta, source } = message.data;
        updateUserCoins(coins);
        toast.success(`+${delta} coins from ${source}!`, {
          icon: <Coins className="w-4 h-4 text-amber-500" />
        });
      } else if (message.type === 'leaderboard_update') {
        setLeaderboard(message.data);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setSocket(null);
    };

    return () => {
      ws.close();
    };
  }, [userId, updateUserCoins]);

  return { socket, leaderboard };
};

// Components
const LoginForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    name: '',
    email: 'admin@vitacoin.com',
    password: 'admin123'
  });
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const result = isLogin 
      ? await login(formData.email, formData.password)
      : await register(formData.name, formData.email, formData.password);

    if (!result.success) {
      toast.error(result.message);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-8 shadow-2xl border-0 bg-white/90 backdrop-blur-sm">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-gradient-to-r from-amber-400 to-orange-500 p-3 rounded-full">
              <Coins className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
            Vitacoin Rewards
          </h1>
          <p className="text-gray-600 mt-2">
            {isLogin ? 'Welcome back!' : 'Join the rewards platform'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <Input
              placeholder="Full Name"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              required
              className="h-12"
            />
          )}
          <Input
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={(e) => setFormData({...formData, email: e.target.value})}
            required
            className="h-12"
          />
          <Input
            type="password"
            placeholder="Password"
            value={formData.password}
            onChange={(e) => setFormData({...formData, password: e.target.value})}
            required
            className="h-12"
          />
          
          <Button 
            type="submit" 
            className="w-full h-12 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-semibold"
            disabled={loading}
          >
            {loading ? 'Loading...' : (isLogin ? 'Sign In' : 'Sign Up')}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-amber-600 hover:text-amber-700 font-medium"
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>

        <div className="mt-6 p-4 bg-amber-50 rounded-lg">
          <p className="text-sm text-amber-800 font-medium">Demo Credentials:</p>
          <p className="text-xs text-amber-700">Email: admin@vitacoin.com</p>
          <p className="text-xs text-amber-700">Password: admin123</p>
        </div>
      </Card>
    </div>
  );
};

const DailyRewardButton = () => {
  const [loading, setLoading] = useState(false);
  const [canClaim, setCanClaim] = useState(true);
  const [nextRewardIn, setNextRewardIn] = useState(0);
  const { user } = useAuth();

  useEffect(() => {
    if (user?.last_daily_reward) {
      const lastReward = new Date(user.last_daily_reward);
      const now = new Date();
      const hoursSince = (now - lastReward) / (1000 * 60 * 60);
      
      if (hoursSince < 24) {
        setCanClaim(false);
        setNextRewardIn(Math.ceil(24 - hoursSince));
      }
    }
  }, [user]);

  const claimDailyReward = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/rewards/daily`);
      if (response.data.success) {
        toast.success(response.data.message);
        setCanClaim(false);
        setNextRewardIn(24);
      } else {
        toast.error(response.data.message);
        setNextRewardIn(response.data.next_reward_in || 0);
      }
    } catch (error) {
      toast.error('Failed to claim daily reward');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6 bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-emerald-800 flex items-center gap-2">
            <Gift className="w-5 h-5" />
            Daily Reward
          </h3>
          <p className="text-sm text-emerald-600">
            {canClaim ? 'Claim your daily +10 coins!' : `Next reward in ${nextRewardIn} hours`}
          </p>
        </div>
        <Button
          onClick={claimDailyReward}
          disabled={!canClaim || loading}
          className="bg-emerald-500 hover:bg-emerald-600 text-white px-6"
        >
          {loading ? 'Claiming...' : canClaim ? 'Claim +10' : <Clock className="w-4 h-4" />}
        </Button>
      </div>
    </Card>
  );
};

const BalanceCard = ({ coins }) => {
  const [displayCoins, setDisplayCoins] = useState(coins);

  useEffect(() => {
    // Animate coin count changes
    if (coins !== displayCoins) {
      const increment = coins > displayCoins ? 1 : -1;
      const timer = setInterval(() => {
        setDisplayCoins(prev => {
          if (prev === coins) {
            clearInterval(timer);
            return prev;
          }
          return prev + increment;
        });
      }, 50);
      return () => clearInterval(timer);
    }
  }, [coins, displayCoins]);

  return (
    <Card className="p-6 bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-amber-600 font-medium">Your Balance</p>
          <div className="flex items-center gap-2 mt-1">
            <Coins className="w-6 h-6 text-amber-500" />
            <span className="text-3xl font-bold text-amber-800">{displayCoins.toLocaleString()}</span>
          </div>
        </div>
        <div className="text-right">
          <Badge variant="secondary" className="bg-amber-100 text-amber-800">
            Vitacoins
          </Badge>
        </div>
      </div>
    </Card>
  );
};

const LeaderboardWidget = ({ leaderboard }) => {
  const [localLeaderboard, setLocalLeaderboard] = useState([]);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const response = await axios.get(`${API}/leaderboard`);
        setLocalLeaderboard(response.data);
      } catch (error) {
        console.error('Failed to fetch leaderboard:', error);
      }
    };

    fetchLeaderboard();
  }, []);

  useEffect(() => {
    if (leaderboard.length > 0) {
      setLocalLeaderboard(leaderboard);
    }
  }, [leaderboard]);

  const getRankIcon = (rank) => {
    switch (rank) {
      case 1: return <Crown className="w-5 h-5 text-yellow-500" />;
      case 2: return <Trophy className="w-5 h-5 text-gray-400" />;
      case 3: return <Star className="w-5 h-5 text-amber-600" />;
      default: return <span className="w-5 h-5 flex items-center justify-center text-sm font-bold text-gray-500">#{rank}</span>;
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-5 h-5 text-blue-500" />
        <h3 className="font-semibold text-gray-800">Top Players</h3>
        <Badge variant="outline" className="ml-auto">Live</Badge>
      </div>
      
      <div className="space-y-3">
        {localLeaderboard.slice(0, 5).map((player) => (
          <div key={player.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              {getRankIcon(player.rank)}
              <span className="font-medium text-gray-800">{player.name}</span>
            </div>
            <div className="flex items-center gap-1 text-amber-600">
              <Coins className="w-4 h-4" />
              <span className="font-semibold">{player.coins.toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

const TransactionsTable = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        const response = await axios.get(`${API}/transactions`);
        setTransactions(response.data);
      } catch (error) {
        console.error('Failed to fetch transactions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchTransactions();
  }, []);

  if (loading) {
    return (
      <Card className="p-6">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-4 bg-gray-200 rounded"></div>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h3 className="font-semibold text-gray-800 mb-4">Recent Transactions</h3>
      <div className="space-y-3">
        {transactions.slice(0, 10).map((tx) => (
          <div key={tx.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium text-gray-800">{tx.description}</p>
              <p className="text-sm text-gray-500">
                {new Date(tx.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className={`flex items-center gap-1 font-semibold ${
              tx.type === 'credit' ? 'text-green-600' : 'text-red-600'
            }`}>
              <Coins className="w-4 h-4" />
              <span>{tx.type === 'credit' ? '+' : '-'}{Math.abs(tx.amount)}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

const Dashboard = () => {
  const { user, logout } = useAuth();
  const { leaderboard } = useWebSocket(user?.id);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-r from-amber-400 to-orange-500 p-2 rounded-lg">
                <Coins className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
                Vitacoin Rewards
              </h1>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-gray-700">
                <Users className="w-4 h-4" />
                <span className="font-medium">{user?.name}</span>
                {user?.role === 'admin' && (
                  <Badge className="bg-purple-100 text-purple-800">Admin</Badge>
                )}
              </div>
              <Button 
                variant="outline" 
                onClick={logout}
                className="text-gray-600 hover:text-gray-800"
              >
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            <BalanceCard coins={user?.coins || 0} />
            <DailyRewardButton />
            
            <Tabs defaultValue="transactions" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="transactions">Transactions</TabsTrigger>
                <TabsTrigger value="badges">Badges</TabsTrigger>
              </TabsList>
              
              <TabsContent value="transactions" className="mt-6">
                <TransactionsTable />
              </TabsContent>
              
              <TabsContent value="badges" className="mt-6">
                <Card className="p-6">
                  <h3 className="font-semibold text-gray-800 mb-4">Your Badges</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {user?.badges?.length > 0 ? (
                      user.badges.map((badge, index) => (
                        <div key={index} className="text-center p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg">
                          <Trophy className="w-8 h-8 text-blue-500 mx-auto mb-2" />
                          <p className="text-sm font-medium text-blue-800">{badge}</p>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-full text-center py-8 text-gray-500">
                        <Trophy className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                        <p>No badges earned yet</p>
                        <p className="text-sm">Complete tasks to unlock badges!</p>
                      </div>
                    )}
                  </div>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
          
          {/* Sidebar */}
          <div className="space-y-6">
            <LeaderboardWidget leaderboard={leaderboard} />
          </div>
        </div>
      </main>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <div className="App">
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginComponent />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster 
          position="top-right"
          richColors
          closeButton
        />
      </div>
    </AuthProvider>
  );
}

const LoginComponent = () => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
      </div>
    );
  }
  
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <LoginForm />;
};

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

export default App;