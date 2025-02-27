from walmart_ca.api_client import WalmartCanadaAPIClient

# Initialize the Walmart API Client
client = WalmartCanadaAPIClient(
    client_id="your_client_id",
    private_key="path_to_your_private_key",
    channel_type="your_channel_type"
)

# Test the API request
try:
    response = client.make_request(
        method="GET",
        endpoint="orders",
        params={"createdStartDate": "2025-01-02"}
    )
    print("API Response:", response)
except RuntimeError as e:
    print("Error:", e)
