from pydantic import BaseModel

class SignupRequest(BaseModel):
    email:str
    password:str

class LoginRequest(BaseModel):
    email:str
    password:str

class GenerateCVRequest(BaseModel):
    company:str=""
    job_title:str=""
    job_description:str
    model:str="llama3.1:8b"