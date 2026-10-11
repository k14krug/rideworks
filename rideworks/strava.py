"""Explicit single-rider OAuth/manual sync. No polling or secrets in reports."""
from contextlib import contextmanager
import base64
import fcntl
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
from pathlib import Path
import secrets
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import webbrowser

from .strava_api import SyncError, absolute, apply_observations, normalize, sync_window

SCOPE = 'activity:read_all'
MAX_JSON = 2*1024*1024
PAGE_SIZE = 100
STREAM_KEYS = ('time', 'watts', 'heartrate', 'cadence', 'moving')
MAX_STREAM_JSON = 16*1024*1024  # Five arrays for long rides; finite, separate from summaries.


class AuthenticationError(SyncError):
    pass


class OperationBusyError(SyncError):
    pass


class ApiError(SyncError):
    def __init__(self,message,status=None,rate=None):
        super().__init__(message)
        self.status,self.rate=status,rate or {}


def rate_state(headers):
    result = {}
    for name in ('X-RateLimit-Limit','X-RateLimit-Usage','X-ReadRateLimit-Limit','X-ReadRateLimit-Usage'):
        value = headers.get(name)
        if value is None:
            continue
        try:
            pair = [int(v.strip()) for v in value.split(',')]
            if len(pair)!=2 or min(pair)<0:
                raise ValueError
        except (ValueError,AttributeError):
            raise SyncError('Invalid Strava rate-limit header') from None
        result[name] = pair
    return result


def exhausted(rate):
    return any(any(used>=limit for used,limit in zip(rate.get(usage,[]),rate.get(limits,[])))
               for limits,usage in [('X-RateLimit-Limit','X-RateLimit-Usage'),
                                     ('X-ReadRateLimit-Limit','X-ReadRateLimit-Usage')])


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        # Never forward credentials to a redirect destination.
        return None


class ApiClient:
    def __init__(self,credentials,*,opener=None):
        self.client_id,self.client_secret=credentials
        self.opener=opener or build_opener(NoRedirect())
        self.rate={}
        self.stream_requests=0
        self.summary_requests=0

    def request(self,method,url,*,form=None,token=None,basic=False,empty=False,max_json=MAX_JSON):
        allowed={'https://www.strava.com/oauth/token','https://www.strava.com/oauth/revoke',
                 'https://www.strava.com/api/v3/athlete/activities'}
        endpoint=url.split('?',1)[0]
        stream_endpoint=re.fullmatch(r'https://www\.strava\.com/api/v3/activities/[1-9][0-9]*/streams',endpoint)
        summary_endpoint=re.fullmatch(r'https://www\.strava\.com/api/v3/activities/[1-9][0-9]{0,19}',endpoint)
        if endpoint not in allowed and not (method=='GET' and (stream_endpoint or summary_endpoint)):
            raise SyncError('Unsupported Strava endpoint')
        if exhausted(self.rate):
            raise ApiError('Strava rate limit exhausted; sync stopped without retry',429,self.rate)
        headers={'User-Agent':'RideWorks/Phase2 (private single-rider manual sync)', 'Accept':'application/json'}
        if token:
            headers['Authorization']='Bearer '+token
        if basic:
            headers['Authorization']='Basic '+base64.b64encode((self.client_id+':'+self.client_secret).encode()).decode()
        data=urlencode(form).encode() if form is not None else None
        if data is not None:
            headers['Content-Type']='application/x-www-form-urlencoded'
        request=Request(url,data=data,headers=headers,method=method)
        if stream_endpoint:self.stream_requests+=1
        if summary_endpoint:self.summary_requests+=1
        try:
            response=self.opener.open(request,timeout=20)
            with response:
                self.rate.update(rate_state(response.headers))
                if response.status!=200:
                    raise ApiError('Strava returned an unexpected HTTP status',response.status,self.rate)
                payload=response.read(max_json+1)
        except HTTPError as error:
            self.rate.update(rate_state(error.headers))
            status=error.code
            error.close()
            if status==401 or (status==400 and url.endswith('/oauth/token')):
                raise AuthenticationError('Strava authorization is invalid or revoked; reconnect') from None
            message='Strava rate limit reached; sync stopped without retry' if status==429 else 'Strava HTTP request failed; no sync changes committed'
            raise ApiError(message,status,self.rate) from None
        except (URLError,OSError,TimeoutError):
            raise SyncError('Strava connection failed or timed out; no sync changes committed') from None
        if len(payload)>max_json:
            raise SyncError('Strava JSON response exceeds the supported size')
        if empty and not payload:
            return {}
        try:
            return json.loads(payload,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError,UnicodeError):
            raise SyncError('Strava returned invalid JSON') from None

    def token(self,**fields):
        return self.request('POST','https://www.strava.com/oauth/token',
                            form=dict(client_id=self.client_id,client_secret=self.client_secret,**fields))

    def activities(self,access_token,window,page):
        query=urlencode(dict(after=window['after'],before=window['before'],page=page,per_page=PAGE_SIZE))
        return self.request('GET','https://www.strava.com/api/v3/athlete/activities?'+query,token=access_token)

    def streams(self,access_token,external_id):
        identity=str(external_id)
        if not re.fullmatch(r'[1-9][0-9]{0,19}',identity):
            raise SyncError('Invalid Strava stream identity')
        query=urlencode(dict(keys=','.join(STREAM_KEYS),key_by_type='true'))
        return self.request('GET',f'https://www.strava.com/api/v3/activities/{identity}/streams?'+query,
                            token=access_token,max_json=MAX_STREAM_JSON)

    def activity_summary(self,access_token,external_id):
        """Explicit established-ID maintenance only; normal sync uses listing."""
        identity=str(external_id)
        if not re.fullmatch(r'[1-9][0-9]{0,19}',identity):
            raise SyncError('Invalid Strava summary identity')
        return self.request('GET',f'https://www.strava.com/api/v3/activities/{identity}',token=access_token)

    def revoke(self,refresh_token):
        return self.request('POST','https://www.strava.com/oauth/revoke',
                            form=dict(token=refresh_token,token_type_hint='refresh_token'),basic=True,empty=True)


class TokenFile:
    def __init__(self,data_dir):
        self.root=Path(data_dir)
        self.path=self.root/'.strava-tokens.json'

    @contextmanager
    def lock(self):
        descriptor=os.open(self.root/'.strava.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise OperationBusyError('Another Strava command is running for this store') from None
            yield
        finally:
            os.close(descriptor)

    def read(self):
        if not self.path.exists():
            raise AuthenticationError('Strava is disconnected; connect Strava first')
        try:
            value=json.loads(self.path.read_text())
            if not isinstance(value,dict) or value.get('scope')!=SCOPE or type(value.get('athlete_id')) is not int:
                raise ValueError
            _validate_tokens(value)
            os.chmod(self.path,0o600)
            return value
        except (ValueError,OSError):
            raise AuthenticationError('Local Strava connection state is invalid; reconnect') from None

    def save(self,value):
        descriptor,temporary=tempfile.mkstemp(prefix='.strava-token-',dir=self.root)
        try:
            with os.fdopen(descriptor,'w') as stream:
                json.dump(value,stream,sort_keys=True,allow_nan=False)
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
            descriptor=os.open(self.root,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)

    def clear(self):
        self.path.unlink(missing_ok=True)


def _validate_tokens(value):
    if not isinstance(value,dict) or type(value.get('expires_at')) is not int or value['expires_at']<1:
        raise AuthenticationError('Invalid Strava token response; reconnect')
    if any(not isinstance(value.get(k),str) or not value[k] or len(value[k])>4096 for k in ('access_token','refresh_token')):
        raise AuthenticationError('Invalid Strava token response; reconnect')


def callback_values(query,state):
    try:
        values=parse_qs(query,max_num_fields=10)
        if any(len(v)!=1 for v in values.values()):raise ValueError
    except ValueError:
        raise AuthenticationError('Invalid Strava authorization callback') from None
    if not secrets.compare_digest(values.get('state',[''])[0].encode(),state.encode()):
        raise AuthenticationError('Strava authorization state mismatch')
    if values.get('error') or not values.get('code'):
        raise AuthenticationError('Strava authorization was declined or incomplete')
    scopes=set(values.get('scope',[''])[0].replace(',', ' ').split())
    if SCOPE not in scopes:
        raise AuthenticationError('Strava activity:read_all permission is required; reconnect and grant it')
    return values['code'][0],sorted(scopes)


def complete_connect(store,client,code,scopes):
    """Shared code exchange/identity validation; caller holds the store token lock."""
    tokens=TokenFile(store.data_dir)
    response=client.token(grant_type='authorization_code',code=code)
    _validate_tokens(response)
    athlete=response.get('athlete')
    athlete=athlete.get('id') if isinstance(athlete,dict) else None
    if type(athlete) is not int or athlete<1:
        raise AuthenticationError('Strava authorization did not identify the authenticated athlete')
    if 'scope' in response and (not isinstance(response['scope'],str) or SCOPE not in set(response['scope'].replace(',',' ').split())):
        raise AuthenticationError('Strava token did not grant activity:read_all')
    checkpoint=store.connection.execute('SELECT athlete_id FROM strava_sync_state WHERE singleton=1').fetchone()
    if checkpoint and checkpoint[0]!=str(athlete):
        raise AuthenticationError('Connected athlete differs from the store; authorize the original account')
    tokens.save({k:response[k] for k in ('access_token','refresh_token','expires_at')} | dict(athlete_id=athlete,scope=SCOPE,granted_scopes=scopes))
    return dict(status='connected',scope=SCOPE)


def authorization_url(client_id,callback,state):
    return 'https://www.strava.com/oauth/authorize?'+urlencode(dict(
        client_id=client_id,redirect_uri=callback,response_type='code',
        approval_prompt='force',scope=SCOPE,state=state))


def connect(store,client,*,port=8772,timeout=180,open_browser=webbrowser.open):
    state=secrets.token_urlsafe(32)
    captured={}
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path!='/strava/callback':
                self.send_error(404);return
            try:
                captured['code'],captured['scopes']=callback_values(urlsplit(self.path).query,state)
                message=b'RideWorks authorization received. Return to the terminal.'
                status=200
            except AuthenticationError as error:
                captured['error']=error
                message=b'RideWorks authorization was not completed. Return to the terminal.'
                status=400
            self.send_response(status);self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(message)
        def log_message(self,*args):pass  # Callback URLs contain the one-use code.
    tokens=TokenFile(store.data_dir)
    with tokens.lock():
        try:server=HTTPServer(('127.0.0.1',port),Callback)
        except OSError:raise SyncError('Cannot start the loopback callback; choose another --callback-port') from None
        try:
            server.timeout=1
            callback=f'http://127.0.0.1:{server.server_port}/strava/callback'
            url=authorization_url(client.client_id,callback,state)
            print('Authorize RideWorks in your browser. Loopback callback: '+callback, file=sys.stderr)
            print(url,file=sys.stderr)
            open_browser(url)
            deadline=time.monotonic()+timeout
            while not captured and time.monotonic()<deadline:server.handle_request()
            if not captured:raise AuthenticationError('Strava authorization timed out; check app callback configuration and try strava-connect again')
            if 'error' in captured:raise captured['error']
            complete_connect(store,client,captured['code'],captured['scopes'])
        finally:server.server_close()
    return dict(status='connected',scope=SCOPE)


def refreshed_connection(tokens,client,*,now=None):
    """Shared rotation path; caller holds this store's token lock."""
    timestamp=int(time.time()) if now is None else now
    current=tokens.read()
    try:
        if current['expires_at']<=timestamp+3600:
            response=client.token(grant_type='refresh_token',refresh_token=current['refresh_token'])
            _validate_tokens(response)
            current.update({k:response[k] for k in ('access_token','refresh_token','expires_at')})
            try:tokens.save(current)  # Always retain the latest rotation before further requests.
            except OSError:
                tokens.clear()
                raise AuthenticationError('Cannot retain the rotated Strava token; reconnect') from None
    except AuthenticationError:
        tokens.clear();raise
    return current


def sync(store,client,*,now=None):
    timestamp=int(time.time()) if now is None else now
    tokens=TokenFile(store.data_dir)
    with tokens.lock():
        current=tokens.read()
        window=sync_window(store,current['athlete_id'],timestamp)
        observations={};pages=0
        try:
            current=refreshed_connection(tokens,client,now=timestamp)
            for page in range(1,21):
                payload=client.activities(current['access_token'],window,page);pages+=1
                if not isinstance(payload,list) or len(payload)>PAGE_SIZE:
                    raise SyncError('Strava returned an invalid activity-list page')
                for item in payload:
                    if isinstance(item,dict) and 'athlete' in item:
                        if not isinstance(item['athlete'],dict) or item['athlete'].get('id')!=current['athlete_id']:
                            raise SyncError('Strava activity belongs to an unexpected athlete')
                    values=normalize(item)
                    start=int(absolute(values['start_date']).timestamp())
                    if not window['after']<start<window['before']:
                        raise SyncError('Strava activity lies outside the requested forward window')
                    previous=observations.get(values['id'])
                    if previous is not None and previous!=values:
                        raise SyncError('Conflicting observations during pagination; retry a later manual sync')
                    observations[values['id']]=values
                if len(payload)<PAGE_SIZE:break
            else:raise SyncError('Recent activity window exceeded 20 pages; sync stopped without historical crawl')
        except AuthenticationError:
            tokens.clear();raise
        result=apply_observations(store,list(observations.values()),current['athlete_id'],timestamp)
        from .strava_streams import enrich, recent_candidates
        stream_result=enrich(store,client,current['access_token'],recent_candidates(store,window))
        from .performance import converge_performance
        performance_result=converge_performance(store)
        from .power_curve import converge_curves
        curve_result=converge_curves(store)
    return dict(status='completed',scope=SCOPE,**window,pages_requested=pages,
                api_activities_observed=len(observations),rate_limits=dict(client.rate),**result,**stream_result,**performance_result,**curve_result)


def disconnect(store,client):
    tokens=TokenFile(store.data_dir)
    remote='not_connected'
    with tokens.lock():
        try:
            current=tokens.read()
            try:
                if client is None:remote='not_attempted_credentials_missing'
                else:client.revoke(current['refresh_token']);remote='revoked'
            except SyncError:remote='unconfirmed'
        except AuthenticationError:pass
        finally:tokens.clear()
    return dict(status='disconnected',remote_revocation=remote,history_retained=True)
