def send_get_request(url, params=None, headers=None):
    """
    Sends a GET HTTP request to the given URL.

    Args:
        url (str): The URL to send the GET request to.
        params (dict, optional): Query parameters to include in the request. Defaults to None.
        headers (dict, optional): HTTP headers to include in the request. Defaults to None.

    Returns:
        dict: A dictionary containing the response's status code and data.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the request.
    """
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raises an HTTPError if the response code is 4xx or 5xx
        return {
            "status_code": response.status_code,
            "data": response.json() if response.headers.get('Content-Type') == 'application/json' else response.text
        }
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
