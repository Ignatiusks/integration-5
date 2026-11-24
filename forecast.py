import time, os, mlflow, numpy as np
from mlflow import MlflowClient
from sklearn.linear_model import LinearRegression
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field
from common import event, metrics
@asynccontextmanager
async def lifespan(app):
    mlflow.set_tracking_uri('sqlite:////registry/mlflow.db')
    mlflow.set_registry_uri('sqlite:////registry/mlflow.db')
    client=MlflowClient()
    try: version=client.get_model_version_by_alias('price-model','prod')
    except mlflow.exceptions.MlflowException:
        mlflow.set_experiment('training')
        x=np.array([[20],[40],[60],[80],[100]])
        model=LinearRegression().fit(x,5000+1800*x.ravel())
        with mlflow.start_run():
            info=mlflow.sklearn.log_model(model,'model',registered_model_name='price-model')
        version=client.search_model_versions("name='price-model'")[0]
        client.set_registered_model_alias('price-model','prod',version.version)
    app.state.model=mlflow.sklearn.load_model('models:/price-model@prod'); app.state.version=version.version
    yield
app=FastAPI(lifespan=lifespan)
app.add_api_route('/metrics',metrics,methods=['GET'])
class Input(BaseModel):
    area:float=Field(gt=0,le=10000)
@app.post('/predict')
def predict(body:Input,x_order_id:str|None=Header(default=None)):
    start=time.monotonic(); price=float(app.state.model.predict(np.array([[body.area]]))[0]); event('predict',predicted_price=price,latency_ms=(time.monotonic()-start)*1000,model_version=app.state.version,order_id=x_order_id)
    return {'predicted_price':price}
