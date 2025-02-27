from django.core.management.base import BaseCommand
from platform_api.platforms.walmart_ca.api import WalmartCAAPI


class Command(BaseCommand):
    help = "Generate signature and timestamp for Walmart Canada API requests with query strings"

    def add_arguments(self, parser):
        parser.add_argument("--endpoint", type=str, required=True, help="API endpoint (e.g., 'orders')")
        parser.add_argument("--method", type=str, required=True, help="HTTP method (e.g., 'GET', 'POST')")

    def handle(self, *args, **kwargs):
        client_id = "a3a150bd-ccd5-43b9-a38c-b2814c1b1b7c"
        private_key = "MIICdQIBADANBgkqhkiG9w0BAQEFAASCAl8wggJbAgEAAoGBAIAbSDAADIkE+ovTA43eWtj6qGbE+Xt112GTUHAD2x0N+9RE2JHJdAIkCypr/wzHZA25q0RvjYw0Mvlt9BwY8Ti+Rmu6cITB1qhc+EMeKHDscvoaVULLYZdrbA4zoy1sLR6ktLNIxMPRSj5g5b2ELil1Y6C0ChFQ3ZVWunHqsFtTAgMBAAECgYBZHqGhguc1ixkhnLKkR0O8HuR4Wh+VG+2yG+Ghi40rMUc37I0dHqBtvNVntanBIhUg10GmYlR+bPHpQ+zGfzOP4eCf/S37qUzysmnq1hNY+eIP+pzl7s0vH+lNq92fJ0yD8m44pb8DADuhCCHyAxemfi57T5mdPAAcQsR7HQP+wQJBALy0BpkHO3BmqhaWvlxLBIjVmFJjpre1Vy0CGveKnjHyyJAIZ86BsZ/U90RcCy8oWNtVDr9878HMOy8qzXczGk8CQQCtyvvlGEpmdOl7AF8ovgePFJbwtDNkYHt3Asg3ld6p4PjJmWk8xKlakViE9eWxR4YuZnhzjs+XzBV0mFLpomG9AkAt8JoGmVckJypTc4GGkJDbCz0ZGb+Vy+UcRP3xs+KNgHDJd/JluPdYVQ2Zq9rhMS5ov01m2vC3upPSCNaapWtLAkBkfQflUYRDdbpC2tYq8qXgP2F/UFKe6YK6L6uhKFEVHPX9a20ELBpYOc5bIutq9BZL4ggnmR3DgceuIR1f5fppAkBEU4wSw/k2LDmwWv08Vn5mhXld2qq10aG9fstvwyIzO2aDRXbzWd2C4RacX2p/lGUo00O6FNgTAL+dG3mbArWe"
        channel_type = "d62e611e-606e-41b9-96cf-38ee37331c47"

        endpoint = kwargs.get("endpoint")
        method = kwargs.get("method")

        # Query string for createdStartDate
        params = {"createdStartDate": "2025-01-02"}

        client = WalmartCAAPI(client_id, private_key, channel_type)

        # Construct the full URL
        url = f"{client.BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            # Generate signature and timestamp
            signature, timestamp = client._generate_signature(url, method, params)
            self.stdout.write(f"Generated Signature: {signature}")
            self.stdout.write(f"Generated Timestamp: {timestamp}")
            self.stdout.write("Use these values in your Postman headers:")
            self.stdout.write(f"WM_SEC.AUTH_SIGNATURE: {signature}")
            self.stdout.write(f"WM_SEC.TIMESTAMP: {timestamp}")
            self.stdout.write(f"Full URL for Postman: {url}?createdStartDate=2025-01-01")
        except Exception as e:
            self.stderr.write(f"Error generating signature: {str(e)}")
