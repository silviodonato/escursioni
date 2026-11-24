import unittest,tempfile,os,json,io,contextlib,importlib.util,importlib.machinery
from pathlib import Path
import ipaddress
import activity_config
activity_config.OWNER='testowner'
activity_config.HOSTS=('nas.test',)
activity_config.NETWORKS=(ipaddress.ip_network('192.168.1.0/24'),)
from unittest.mock import patch
import activity_auth as a
loader=importlib.machinery.SourceFileLoader('session_api',str(Path(__file__).with_name('sessione.cgi')));spec=importlib.util.spec_from_loader(loader.name,loader);api=importlib.util.module_from_spec(spec);loader.exec_module(api)
a.OWNER='testowner';api.guard.OWNER='testowner';api.guard.HOSTS=('nas.test',);api.guard.NETWORKS=activity_config.NETWORKS
class Authentication(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name);self.state_patch=patch.object(a,'STATE',self.state);self.state_patch.start();self.env=patch.dict(os.environ,{'REMOTE_ADDR':'192.168.1.42','HTTP_USER_AGENT':'Test browser'},clear=True);self.env.start()
 def tearDown(self):self.env.stop();self.state_patch.stop();self.tmp.cleanup()
 def test_password_is_verified_and_dsm_session_closed(self):
  calls=[]
  def dsm(params):
   calls.append(params)
   return {'success':True,'data':{'sid':'temporary-dsm-session'}} if params['method']=='login' else {'success':True}
  with patch.object(a,'dsm_api',side_effect=dsm):value=a.login('test-password')
  self.assertEqual(calls[0]['account'],'testowner');self.assertEqual(calls[0]['passwd'],'test-password');self.assertEqual(calls[1]['method'],'logout');self.assertEqual(calls[1]['_sid'],'temporary-dsm-session')
  stored=''.join(p.read_text() for p in self.state.rglob('*.json'))
  self.assertNotIn('test-password',stored);self.assertNotIn('temporary-dsm-session',stored);self.assertNotIn(value,stored)
  os.environ['HTTP_COOKIE']=a.COOKIE+'='+value;self.assertTrue(a.valid_session())
 def test_bad_password_never_issues_session(self):
  with patch.object(a,'dsm_api',return_value={'success':False,'error':{'code':400}}):
   with self.assertRaises(a.LoginError):a.login('wrong')
  self.assertFalse((self.state/'sessions').exists())
 def test_otp_challenge_and_otp_failure(self):
  for code in (403,404,406):
   with patch.object(a,'dsm_api',return_value={'success':False,'error':{'code':code}}):
    with self.assertRaises(a.LoginError) as error:a.login('test-password')
    self.assertTrue(error.exception.otp)
 def test_incomplete_dsm_verification_never_issues_session(self):
  with patch.object(a,'dsm_api',side_effect=[{'success':True,'data':{'sid':'sid'}},{'success':False}]):
   with self.assertRaises(a.LoginError):a.login('test-password')
  self.assertFalse((self.state/'sessions').exists())
 def test_session_expiry_revocation_and_client_binding(self):
  value=a.issue_session();os.environ['HTTP_COOKIE']=a.COOKIE+'='+value;self.assertTrue(a.valid_session());a.revoke_session();self.assertFalse(a.valid_session())
  value=a.issue_session();os.environ['HTTP_COOKIE']=a.COOKIE+'='+value
  with patch.object(a.time,'time',return_value=10**12):self.assertFalse(a.valid_session())
  value=a.issue_session();os.environ['HTTP_COOKIE']=a.COOKIE+'='+value;os.environ['REMOTE_ADDR']='192.168.1.43';self.assertFalse(a.valid_session())
 def test_reject_malformed_cookie_and_session_symlink(self):
  for value in ('../x','a'*44,'bad'):
   os.environ['HTTP_COOKIE']=a.COOKIE+'='+value;self.assertFalse(a.valid_session())
  value=a.issue_session();path=a.session_path(value);raw=path.read_bytes();path.unlink();other=self.state/'other.json';other.write_bytes(raw);path.symlink_to(other);os.environ['HTTP_COOKIE']=a.COOKIE+'='+value;self.assertFalse(a.valid_session())
 def test_cookie_is_httponly_strict_scoped_and_short_lived(self):
  header=a.cookie_header('test');self.assertIn('HttpOnly',header);self.assertIn('SameSite=Strict',header);self.assertIn('Path=/escursioni/',header);self.assertIn('Max-Age=1800',header)
  os.environ['HTTPS']='on';self.assertIn('; Secure',a.cookie_header('test'))
 def test_rate_limit_stops_sixth_attempt(self):
  for _ in range(5):a.rate_check()
  with self.assertRaises(a.LoginError) as error:a.rate_check()
  self.assertEqual(error.exception.code,429)
 def request(self,changes=None,body='{"action":"login","password":"test-password"}'):
  env={'REMOTE_ADDR':'192.168.1.42','HTTP_USER_AGENT':'Test browser','REQUEST_METHOD':'POST','HTTP_HOST':'nas.test','HTTP_ORIGIN':'http://nas.test','HTTP_X_ESCURSIONI_ACTION':'activity-login','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body))};env.update(changes or {});output=io.StringIO()
  with patch.dict(os.environ,env,clear=True),patch.object(api.sys,'stdin',io.StringIO(body)),patch.object(a,'login',return_value='x'*43) as login,contextlib.redirect_stdout(output):api.main()
  return output.getvalue(),login.called
 def test_only_direct_local_same_origin_post_can_log_in(self):
  for changes in ({'REMOTE_ADDR':'8.8.8.8'},{'HTTP_X_FORWARDED_FOR':'192.168.1.42'},{'HTTP_ORIGIN':'http://other.test'},{'HTTP_HOST':'public.example.test','HTTP_ORIGIN':'https://public.example.test'},{'HTTP_X_ESCURSIONI_ACTION':'manage-activity'}):
   output,called=self.request(changes);self.assertIn('403 Forbidden',output);self.assertFalse(called)
  output,called=self.request({'REQUEST_METHOD':'GET'});self.assertIn('405 Method Not Allowed',output);self.assertFalse(called)
 def test_login_response_sets_cookie_and_does_not_return_password(self):
  output,called=self.request();self.assertTrue(called);self.assertIn('Set-Cookie: escursioni_admin=',output);self.assertNotIn('test-password',output);self.assertTrue(json.loads(output.split('\n\n')[1])['ok'])
 def test_validation_error_keeps_json_message_through_nginx(self):
  env={'REQUEST_METHOD':'POST','REMOTE_ADDR':'192.168.1.42','HTTP_HOST':'nas.test','HTTP_ORIGIN':'http://nas.test','HTTP_X_ESCURSIONI_ACTION':'activity-login','CONTENT_TYPE':'application/json','CONTENT_LENGTH':'18'};out=io.StringIO()
  with patch.dict(os.environ,env,clear=True),patch.object(api.sys,'stdin',io.StringIO('{"action":"login"}')),patch.object(a,'login',side_effect=a.LoginError('Password non corretta.')),contextlib.redirect_stdout(out):api.main()
  self.assertIn('Status: 200 OK',out.getvalue());data=json.loads(out.getvalue().split('\n\n')[1]);self.assertFalse(data['ok']);self.assertEqual(data['code'],401)
if __name__=='__main__':unittest.main(verbosity=2)
