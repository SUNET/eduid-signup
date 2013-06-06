from pwgen import pwgen

import vccs_client


def generate_password(vccs_uri, credential_id, email):
    password = pwgen(20, no_symbols=True)
    factor = vccs_client.VCCSPasswordFactor(password,
                                            credential_id=credential_id)
    vccs = vccs_client.VCCSClient(base_url=vccs_uri)
    vccs.add_credentials(email, [factor])
    return (password, factor.salt)
