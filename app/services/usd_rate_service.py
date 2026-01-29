import requests


def get_usd_rate():
    try:
        response = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL", timeout=10)
        data = response.json()
        return float(data["USDBRL"]["bid"])
    except Exception as e:
        print(f"Erro ao buscar câmbio: {e}")
        return 5.50
