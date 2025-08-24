import requests
import sys
import json
from datetime import datetime
import time

class VitacoinAPITester:
    def __init__(self, base_url="https://uvrp-app.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.user_token = None
        self.test_user_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, description=""):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        if description:
            print(f"   Description: {description}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    elif isinstance(response_data, list) and len(response_data) > 0:
                        print(f"   Response: {len(response_data)} items returned")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:200]}...")

            return success, response.json() if response.content else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_database_initialization(self):
        """Test database initialization"""
        success, response = self.run_test(
            "Database Initialization",
            "POST",
            "admin/init-db",
            200,
            description="Initialize database with default admin user and reward rules"
        )
        return success

    def test_admin_login(self):
        """Test admin login with demo credentials"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@vitacoin.com", "password": "admin123"},
            description="Login with demo admin credentials"
        )
        if success and 'access_token' in response:
            self.admin_token = response['access_token']
            print(f"   Admin token obtained: {self.admin_token[:20]}...")
            return True
        return False

    def test_user_registration(self):
        """Test user registration"""
        timestamp = int(time.time())
        test_email = f"testuser{timestamp}@example.com"
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "name": f"Test User {timestamp}",
                "email": test_email,
                "password": "testpass123"
            },
            description="Register a new test user"
        )
        
        if success:
            self.test_user_id = response.get('id')
            # Now login with the new user
            login_success, login_response = self.run_test(
                "New User Login",
                "POST",
                "auth/login",
                200,
                data={"email": test_email, "password": "testpass123"},
                description="Login with newly registered user"
            )
            if login_success and 'access_token' in login_response:
                self.user_token = login_response['access_token']
                print(f"   User token obtained: {self.user_token[:20]}...")
                return True
        return False

    def test_auth_me(self):
        """Test getting current user info"""
        if not self.admin_token:
            print("❌ Skipping auth/me test - no admin token")
            return False
            
        success, response = self.run_test(
            "Get Current User Info",
            "GET",
            "auth/me",
            200,
            token=self.admin_token,
            description="Get current authenticated user information"
        )
        return success

    def test_daily_reward_claim(self):
        """Test daily reward claiming (should show cooldown for admin)"""
        if not self.admin_token:
            print("❌ Skipping daily reward test - no admin token")
            return False
            
        success, response = self.run_test(
            "Daily Reward Claim",
            "POST",
            "rewards/daily",
            200,  # Should return 200 even if on cooldown
            token=self.admin_token,
            description="Attempt to claim daily reward (should show cooldown)"
        )
        
        if success:
            if response.get('success') == False and 'cooldown' in response.get('message', '').lower():
                print("   ✅ Cooldown behavior working correctly")
            elif response.get('success') == True:
                print("   ✅ Daily reward claimed successfully")
            return True
        return False

    def test_user_daily_reward(self):
        """Test daily reward claiming with new user (should succeed)"""
        if not self.user_token:
            print("❌ Skipping user daily reward test - no user token")
            return False
            
        success, response = self.run_test(
            "New User Daily Reward",
            "POST",
            "rewards/daily",
            200,
            token=self.user_token,
            description="Claim daily reward with new user (should succeed)"
        )
        return success

    def test_transactions(self):
        """Test getting user transactions"""
        if not self.admin_token:
            print("❌ Skipping transactions test - no admin token")
            return False
            
        success, response = self.run_test(
            "Get User Transactions",
            "GET",
            "transactions",
            200,
            token=self.admin_token,
            description="Get transaction history for current user"
        )
        return success

    def test_leaderboard(self):
        """Test getting leaderboard (public endpoint)"""
        success, response = self.run_test(
            "Get Leaderboard",
            "GET",
            "leaderboard",
            200,
            description="Get public leaderboard (no auth required)"
        )
        return success

    def test_admin_users(self):
        """Test admin endpoint to get all users"""
        if not self.admin_token:
            print("❌ Skipping admin users test - no admin token")
            return False
            
        success, response = self.run_test(
            "Admin - Get All Users",
            "GET",
            "admin/users",
            200,
            token=self.admin_token,
            description="Admin endpoint to get all users"
        )
        return success

    def test_admin_rules(self):
        """Test admin endpoint to get reward rules"""
        if not self.admin_token:
            print("❌ Skipping admin rules test - no admin token")
            return False
            
        success, response = self.run_test(
            "Admin - Get Reward Rules",
            "GET",
            "admin/rules",
            200,
            token=self.admin_token,
            description="Admin endpoint to get all reward rules"
        )
        return success

    def test_unauthorized_access(self):
        """Test that admin endpoints require proper authorization"""
        success, response = self.run_test(
            "Unauthorized Admin Access",
            "GET",
            "admin/users",
            401,  # Should return 401 Unauthorized
            description="Test admin endpoint without token (should fail)"
        )
        return success

    def test_user_admin_access(self):
        """Test that regular user cannot access admin endpoints"""
        if not self.user_token:
            print("❌ Skipping user admin access test - no user token")
            return False
            
        success, response = self.run_test(
            "User Admin Access Denied",
            "GET",
            "admin/users",
            403,  # Should return 403 Forbidden
            token=self.user_token,
            description="Test admin endpoint with user token (should be forbidden)"
        )
        return success

def main():
    print("🚀 Starting Vitacoin Rewards Platform API Tests")
    print("=" * 60)
    
    tester = VitacoinAPITester()
    
    # Test sequence
    tests = [
        ("Database Initialization", tester.test_database_initialization),
        ("Admin Login", tester.test_admin_login),
        ("User Registration & Login", tester.test_user_registration),
        ("Get Current User Info", tester.test_auth_me),
        ("Daily Reward Claim (Admin)", tester.test_daily_reward_claim),
        ("Daily Reward Claim (New User)", tester.test_user_daily_reward),
        ("Get Transactions", tester.test_transactions),
        ("Get Leaderboard", tester.test_leaderboard),
        ("Admin - Get Users", tester.test_admin_users),
        ("Admin - Get Rules", tester.test_admin_rules),
        ("Unauthorized Access Test", tester.test_unauthorized_access),
        ("User Admin Access Test", tester.test_user_admin_access),
    ]
    
    print(f"\n📋 Running {len(tests)} test categories...")
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            test_func()
        except Exception as e:
            print(f"❌ Test category failed with exception: {str(e)}")
    
    # Print final results
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "No tests run")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed - check the output above for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())