# from pyngrok import ngrok
# import uvicorn
# import os

# # Set your ngrok auth token
# ngrok.set_auth_token("2nbZ11tGPRzcFiYYEhr0dTCJhXP_3ByJ9NLNtC6ZRrPg5UVpD")

# # Start ngrok tunnel
# http_tunnel = ngrok.connect(8000)
# print(f"Public URL: {http_tunnel.public_url}")

# # Run the FastAPI app
# os.system("uvicorn main:app --host 0.0.0.0 --port 8000")



from pyngrok import ngrok
import uvicorn
import os

# Set your ngrok auth token
ngrok.set_auth_token("")

# Configure ngrok to use your fixed domain
tunnel_config = {
    "domain": "obviously-full-reptile.ngrok-free.app"  # Your fixed domain
}

# Start ngrok tunnel with the fixed domain
http_tunnel = ngrok.connect(8000, **tunnel_config)
print(f"Public URL: {http_tunnel.public_url}")

# Run the FastAPI app
os.system("uvicorn main:app --host 0.0.0.0 --port 8000")