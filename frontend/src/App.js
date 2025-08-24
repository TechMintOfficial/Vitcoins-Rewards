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
import { Progress } from './components/ui/progress';
import { 
  Coins, Trophy, Clock, Users, Gift, TrendingUp, Crown, Star, 
  CheckCircle, Circle, Target, Calendar, Award, Zap, Timer,
  Play, BookOpen, Sparkles, User, AlertCircle, Eye, BarChart3,
  ArrowRight, CheckSquare, Activity
} from 'lucide-react';

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

  const refreshUser = () => {
    fetchUserInfo();
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      login, 
      register, 
      logout, 
      loading, 
      updateUserCoins,
      refreshUser 
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
      } else if (message.type === 'task_completed') {
        const { task_title, coins_earned } = message.data;
        toast.success(`Task completed: ${task_title}`, {
          description: `+${coins_earned} coins earned!`,
          icon: <CheckCircle className="w-4 h-4 text-green-500" />
        });
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
    email: '',
    password: ''
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
      <Card className="w-full max-w-md p-6 sm:p-8 shadow-2xl border-0 bg-white/90 backdrop-blur-sm">
        <div className="text-center mb-6 sm:mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-gradient-to-r from-amber-400 to-orange-500 p-3 rounded-full">
              <Coins className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
            Vitacoin Rewards
          </h1>
          <p className="text-gray-600 mt-2 text-sm sm:text-base">
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
            className="text-amber-600 hover:text-amber-700 font-medium text-sm sm:text-base"
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </Card>
    </div>
  );
};

const DailyRewardButton = () => {
  const [loading, setLoading] = useState(false);
  const [canClaim, setCanClaim] = useState(true);
  const [nextRewardIn, setNextRewardIn] = useState(0);
  const { user, refreshUser } = useAuth();

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
        refreshUser();
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
    <Card className="p-4 sm:p-6 bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-0">
        <div>
          <h3 className="font-semibold text-emerald-800 flex items-center gap-2 text-sm sm:text-base">
            <Gift className="w-4 h-4 sm:w-5 sm:h-5" />
            Daily Reward
          </h3>
          <p className="text-xs sm:text-sm text-emerald-600 mt-1">
            {canClaim ? 'Claim your daily +10 coins!' : `Next reward in ${nextRewardIn} hours`}
          </p>
        </div>
        <Button
          onClick={claimDailyReward}
          disabled={!canClaim || loading}
          className="bg-emerald-500 hover:bg-emerald-600 text-white px-4 sm:px-6 text-sm w-full sm:w-auto"
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
    <Card className="p-4 sm:p-6 bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs sm:text-sm text-amber-600 font-medium">Your Balance</p>
          <div className="flex items-center gap-2 mt-1">
            <Coins className="w-5 h-5 sm:w-6 sm:h-6 text-amber-500" />
            <span className="text-2xl sm:text-3xl font-bold text-amber-800">{displayCoins.toLocaleString()}</span>
          </div>
        </div>
        <div className="text-right">
          <Badge variant="secondary" className="bg-amber-100 text-amber-800 text-xs">
            Vitacoins
          </Badge>
        </div>
      </div>
    </Card>
  );
};

const TaskCard = ({ task, onTaskUpdate }) => {
  const [expanded, setExpanded] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const { refreshUser } = useAuth();

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'daily': return <Calendar className="w-4 h-4 sm:w-5 sm:h-5" />;
      case 'weekly': return <Target className="w-4 h-4 sm:w-5 sm:h-5" />;
      case 'achievement': return <Award className="w-4 h-4 sm:w-5 sm:h-5" />;
      case 'special': return <Sparkles className="w-4 h-4 sm:w-5 sm:h-5" />;
      default: return <Circle className="w-4 h-4 sm:w-5 sm:h-5" />;
    }
  };

  const getDifficultyColor = (difficulty) => {
    switch (difficulty) {
      case 'easy': return 'bg-green-100 text-green-800 border-green-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'hard': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'in_progress': return 'text-blue-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-3 h-3 sm:w-4 sm:h-4" />;
      case 'in_progress': return <Activity className="w-3 h-3 sm:w-4 sm:h-4" />;
      default: return <Circle className="w-3 h-3 sm:w-4 sm:h-4" />;
    }
  };

  const handleClaimTask = async () => {
    setClaiming(true);
    try {
      const response = await axios.post(`${API}/tasks/${task.id}/claim`);
      if (response.data.success) {
        toast.success(response.data.message);
        refreshUser();
        onTaskUpdate(); // Refresh tasks
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to claim task');
    } finally {
      setClaiming(false);
    }
  };

  const trackActivity = async (activityType) => {
    try {
      await axios.post(`${API}/activities/${activityType}`);
      onTaskUpdate(); // Refresh tasks to update progress
    } catch (error) {
      console.error('Failed to track activity:', error);
    }
  };

  const renderActionButtons = () => {
    if (task.is_completed) {
      return (
        <Badge className="bg-green-100 text-green-800 border-green-200 text-xs">
          <CheckCircle className="w-3 h-3 mr-1" />
          Completed
        </Badge>
      );
    }

    if (task.can_claim) {
      return (
        <Button
          onClick={handleClaimTask}
          disabled={claiming}
          className="bg-green-500 hover:bg-green-600 text-white text-xs sm:text-sm"
          size="sm"
        >
          {claiming ? 'Claiming...' : (
            <>
              <CheckSquare className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
              Claim +{task.coins_reward}
            </>
          )}
        </Button>
      );
    }

    // Show action buttons based on task requirements
    if (task.title === "Profile Explorer") {
      return (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => trackActivity('view-transactions')}
            className="text-blue-600 border-blue-200 hover:bg-blue-50 text-xs sm:text-sm"
          >
            <Eye className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
            View Profile
          </Button>
        </div>
      );
    }

    if (task.title === "Social Butterfly") {
      return (
        <Button
          variant="outline"
          size="sm"
          onClick={() => trackActivity('view-leaderboard')}
          className="text-blue-600 border-blue-200 hover:bg-blue-50 text-xs sm:text-sm"
        >
          <BarChart3 className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
          Check Leaderboard
        </Button>
      );
    }

    return (
      <Badge variant="outline" className="text-blue-600 text-xs">
        In Progress
      </Badge>
    );
  };

  return (
    <Card className={`transition-all duration-200 ${expanded ? 'border-blue-200 shadow-md' : 'hover:shadow-sm'}`}>
      <div 
        className="p-3 sm:p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2 sm:gap-3 flex-1">
            <div className={`flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 rounded-full ${
              task.is_completed 
                ? 'bg-green-100' 
                : task.can_claim 
                ? 'bg-blue-100' 
                : 'bg-gray-100'
            }`}>
              {getCategoryIcon(task.category)}
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 sm:gap-2 mb-1 flex-wrap">
                <h4 className="font-medium text-gray-800 text-sm sm:text-base truncate">{task.title}</h4>
                <Badge className={`${getDifficultyColor(task.difficulty)} text-xs`} variant="secondary">
                  {task.difficulty}
                </Badge>
                <Badge variant="outline" className="capitalize text-xs">
                  {task.category}
                </Badge>
              </div>
              
              <p className="text-xs sm:text-sm text-gray-600 mb-2 line-clamp-2">{task.description}</p>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-amber-600">
                  <Coins className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="font-semibold text-xs sm:text-sm">+{task.coins_reward} coins</span>
                </div>
                
                <div className={`flex items-center gap-1 text-xs ${getStatusColor(task.progress?.status)}`}>
                  {getStatusIcon(task.progress?.status)}
                  <span className="capitalize hidden sm:inline">{task.progress?.status || 'pending'}</span>
                </div>
              </div>
            </div>
          </div>
          
          <ArrowRight className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ml-2 ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </div>
      
      {expanded && (
        <div className="px-3 sm:px-4 pb-3 sm:pb-4 border-t bg-gray-50">
          <div className="pt-3 sm:pt-4">
            <div className="mb-3 sm:mb-4">
              <p className="text-xs sm:text-sm text-gray-700 mb-2">
                <strong>Progress:</strong> {task.progress?.description}
              </p>
              
              {task.progress?.status === 'in_progress' && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 sm:p-3 mb-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
                    <div className="text-xs sm:text-sm text-blue-700">
                      <p className="font-medium mb-1">Next Steps:</p>
                      <p>{task.progress.description}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs text-gray-500">
                <span className="hidden sm:inline">Category: {task.category} • Difficulty: {task.difficulty}</span>
                <span className="sm:hidden">{task.category} • {task.difficulty}</span>
              </div>
              {renderActionButtons()}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};

const TasksPanel = () => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const { user } = useAuth();

  const fetchTasks = async () => {
    try {
      const response = await axios.get(`${API}/tasks`);
      setTasks(response.data);
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true;
    return task.category === filter;
  });

  const availableTasks = filteredTasks.filter(task => !task.is_completed);
  const completedTasks = filteredTasks.filter(task => task.is_completed);

  if (loading) {
    return (
      <Card className="p-4 sm:p-6">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 sm:h-16 bg-gray-200 rounded"></div>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <Card className="p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 sm:mb-6 gap-4">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-blue-500" />
            <h3 className="font-semibold text-gray-800 text-sm sm:text-base">Available Tasks</h3>
            <Badge variant="outline" className="text-xs">{availableTasks.length} available</Badge>
          </div>
          
          <div className="flex gap-1 sm:gap-2 overflow-x-auto pb-2 sm:pb-0">
            {['all', 'daily', 'weekly', 'achievement', 'special'].map((cat) => (
              <Button
                key={cat}
                variant={filter === cat ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilter(cat)}
                className="capitalize text-xs sm:text-sm whitespace-nowrap"
              >
                {cat}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-3 sm:space-y-4">
          {availableTasks.length === 0 ? (
            <div className="text-center py-6 sm:py-8 text-gray-500">
              <Target className="w-10 h-10 sm:w-12 sm:h-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm sm:text-base">No tasks available in this category</p>
              <p className="text-xs sm:text-sm">Check back later for new tasks!</p>
            </div>
          ) : (
            availableTasks.map((task) => (
              <TaskCard 
                key={task.id} 
                task={task} 
                onTaskUpdate={fetchTasks}
              />
            ))
          )}
        </div>
      </Card>

      {completedTasks.length > 0 && (
        <Card className="p-4 sm:p-6">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <h3 className="font-semibold text-gray-800 text-sm sm:text-base">Completed Tasks</h3>
            <Badge className="bg-green-100 text-green-800 text-xs">{completedTasks.length} completed</Badge>
          </div>
          
          <div className="space-y-3">
            {completedTasks.map((task) => (
              <TaskCard 
                key={task.id} 
                task={task} 
                onTaskUpdate={fetchTasks}
              />
            ))}
          </div>
        </Card>
      )}
    </div>
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
      case 1: return <Crown className="w-4 h-4 sm:w-5 sm:h-5 text-yellow-500" />;
      case 2: return <Trophy className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400" />;
      case 3: return <Star className="w-4 h-4 sm:w-5 sm:h-5 text-amber-600" />;
      default: return <span className="w-4 h-4 sm:w-5 sm:h-5 flex items-center justify-center text-xs sm:text-sm font-bold text-gray-500">#{rank}</span>;
    }
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 sm:w-5 sm:h-5 text-blue-500" />
        <h3 className="font-semibold text-gray-800 text-sm sm:text-base">Top Players</h3>
        <Badge variant="outline" className="ml-auto text-xs">Live</Badge>
      </div>
      
      <div className="space-y-2 sm:space-y-3">
        {localLeaderboard.slice(0, 5).map((player) => (
          <div key={player.id} className="flex items-center justify-between p-2 sm:p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
              {getRankIcon(player.rank)}
              <span className="font-medium text-gray-800 text-sm sm:text-base truncate">{player.name}</span>
            </div>
            <div className="flex items-center gap-1 text-amber-600 flex-shrink-0">
              <Coins className="w-3 h-3 sm:w-4 sm:h-4" />
              <span className="font-semibold text-xs sm:text-sm">{player.coins.toLocaleString()}</span>
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
      <Card className="p-4 sm:p-6">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-3 sm:h-4 bg-gray-200 rounded"></div>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-4 sm:p-6">
      <h3 className="font-semibold text-gray-800 mb-4 text-sm sm:text-base">Recent Transactions</h3>
      <div className="space-y-2 sm:space-y-3">
        {transactions.slice(0, 10).map((tx) => (
          <div key={tx.id} className="flex items-center justify-between p-2 sm:p-3 bg-gray-50 rounded-lg">
            <div className="min-w-0 flex-1">
              <p className="font-medium text-gray-800 text-sm sm:text-base truncate">{tx.description}</p>
              <p className="text-xs sm:text-sm text-gray-500">
                {new Date(tx.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className={`flex items-center gap-1 font-semibold flex-shrink-0 ml-2 ${
              tx.type === 'credit' ? 'text-green-600' : 'text-red-600'
            }`}>
              <Coins className="w-3 h-3 sm:w-4 sm:h-4" />
              <span className="text-xs sm:text-sm">{tx.type === 'credit' ? '+' : '-'}{Math.abs(tx.amount)}</span>
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
          <div className="flex items-center justify-between h-14 sm:h-16">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="bg-gradient-to-r from-amber-400 to-orange-500 p-1.5 sm:p-2 rounded-lg">
                <Coins className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
              </div>
              <h1 className="text-lg sm:text-xl font-bold bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
                Vitacoin Rewards
              </h1>
            </div>
            
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="flex items-center gap-1 sm:gap-2 text-gray-700">
                <User className="w-4 h-4" />
                <span className="font-medium text-sm sm:text-base hidden sm:inline">{user?.name}</span>
                <span className="font-medium text-sm sm:hidden">{user?.name?.split(' ')[0]}</span>
                {user?.role === 'admin' && (
                  <Badge className="bg-purple-100 text-purple-800 text-xs">Admin</Badge>
                )}
              </div>
              <Button 
                variant="outline" 
                onClick={logout}
                size="sm"
                className="text-gray-600 hover:text-gray-800 text-xs sm:text-sm"
              >
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8">
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
          {/* Main Content */}
          <div className="xl:col-span-3 space-y-4 sm:space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
              <BalanceCard coins={user?.coins || 0} />
              <DailyRewardButton />
            </div>
            
            <Tabs defaultValue="tasks" className="w-full">
              <TabsList className="grid w-full grid-cols-3 h-10 sm:h-11">
                <TabsTrigger value="tasks" className="text-xs sm:text-sm">Tasks</TabsTrigger>
                <TabsTrigger value="transactions" className="text-xs sm:text-sm">Transactions</TabsTrigger>
                <TabsTrigger value="badges" className="text-xs sm:text-sm">Badges</TabsTrigger>
              </TabsList>
              
              <TabsContent value="tasks" className="mt-4 sm:mt-6">
                <TasksPanel />
              </TabsContent>
              
              <TabsContent value="transactions" className="mt-4 sm:mt-6">
                <TransactionsTable />
              </TabsContent>
              
              <TabsContent value="badges" className="mt-4 sm:mt-6">
                <Card className="p-4 sm:p-6">
                  <h3 className="font-semibold text-gray-800 mb-4 text-sm sm:text-base">Your Badges</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
                    {user?.badges?.length > 0 ? (
                      user.badges.map((badge, index) => (
                        <div key={index} className="text-center p-3 sm:p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg">
                          <Trophy className="w-6 h-6 sm:w-8 sm:h-8 text-blue-500 mx-auto mb-2" />
                          <p className="text-xs sm:text-sm font-medium text-blue-800">{badge}</p>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-full text-center py-6 sm:py-8 text-gray-500">
                        <Trophy className="w-10 h-10 sm:w-12 sm:h-12 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm sm:text-base">No badges earned yet</p>
                        <p className="text-xs sm:text-sm">Complete tasks to unlock badges!</p>
                      </div>
                    )}
                  </div>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
          
          {/* Sidebar */}
          <div className="xl:col-span-1 order-first xl:order-last">
            <div className="sticky top-20">
              <LeaderboardWidget leaderboard={leaderboard} />
            </div>
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