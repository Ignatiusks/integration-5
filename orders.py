import time, jwt, httpx, psycopg
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram
from common import secret, event, metrics

counter=Counter('orders_total','Terminal orders',['status'])
for status in ('priced','failed'): counter.labels(status)
latency=Histogram('pricing_seconds','Pricing duration',buckets=(.1,.25,.5,1,2,5,10,20))
def db():
    return psycopg.connect(host='postgres',dbname='orders',user='orders',password=secret('postgres_password'))
@asynccontextmanager
async def lifespan(app):
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, area DOUBLE PRECISION NOT NULL, status TEXT NOT NULL, price DOUBLE PRECISION)')
    yield
app=FastAPI(lifespan=lifespan)
app.add_api_route('/metrics',metrics,methods=['GET'])
class Login(BaseModel):
    password: str
class Order(BaseModel):
    area: float = Field(gt=0,le=10000)
@app.post('/token')
def token(body: Login):
    import hmac
    if not hmac.compare_digest(body.password,secret('login_password')): raise HTTPException(401)
    return {'access_token':jwt.encode({'sub':'student','exp':datetime.now(timezone.utc)+timedelta(hours=2)},secret('jwt_secret'),algorithm='HS256'),'token_type':'bearer'}
def auth(c: HTTPAuthorizationCredentials=Depends(HTTPBearer(auto_error=False))):
    try:
        if c is None: raise ValueError()
        return jwt.decode(c.credentials,secret('jwt_secret'),algorithms=['HS256'])
    except (jwt.InvalidTokenError,ValueError): raise HTTPException(401,'Invalid token',headers={'WWW-Authenticate':'Bearer'})
def pricing(id,area):
    start=time.monotonic(); event('pricing_started',order_id=id)
    price=None; error=None
    for attempt in range(3):
        try:
            r=httpx.post('http://forecast-api:8001/predict',json={'area':area},headers={'X-Order-Id':str(id)},timeout=2); r.raise_for_status(); price=float(r.json()['predicted_price']); error=None; break
        except Exception as e:
            error=str(e)
            if attempt<2: time.sleep(2**attempt)
    status='failed' if error is not None else 'priced'
    try:
        with db() as c:
            result=c.execute("UPDATE orders SET status=%s, price=%s WHERE id=%s AND status='pending'",(status,price,id))
            changed=result.rowcount
        if changed:
            counter.labels(status).inc(); duration=time.monotonic()-start; latency.observe(duration)
            if error is None: event('pricing_succeeded',order_id=id,duration_ms=duration*1000)
            else: event('pricing_failed',level='error',order_id=id,error=error,duration_ms=duration*1000)
    except Exception as e: event('pricing_failed',level='error',order_id=id,error=str(e))
@app.post('/orders',status_code=202)
def create(body:Order,tasks:BackgroundTasks,user=Depends(auth)):
    with db() as c: id=c.execute("INSERT INTO orders(area,status) VALUES (%s,'pending') RETURNING id",(body.area,)).fetchone()[0]
    tasks.add_task(pricing,id,body.area)
    return {'id':id,'status':'pending'}
@app.get('/orders/{id}')
def get(id:int,user=Depends(auth)):
    with db() as c: row=c.execute('SELECT id,area,status,price FROM orders WHERE id=%s',(id,)).fetchone()
    if not row: raise HTTPException(404)
    return dict(zip(('id','area','status','price'),row))
