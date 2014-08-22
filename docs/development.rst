Development
-----------

Mock VCCS backend
    $ pip install turq
    $ python -m turq -p 8550

    Go to http://localhost:8550/+turq/ and paste the snippet below in the textbox and hit the commit button.

    import json
    with path('/add_creds') as r:
        r.body(json.dumps({'add_creds_response': {'version': 1, 'success': True,}}))