import base64
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from starlette.concurrency import run_in_threadpool
from structlog import get_logger
from asn1crypto import core

from src.core.config import EnvironmentOption, settings

log = get_logger(__name__)

GOOGLE_ROOT_CA_PEM = """-----BEGIN CERTIFICATE-----
MIICeDCCAh6gAwIBAgIIdp8/Qz/jN5QwCgYIKoZIzj0EAwIwaDELMAkGA1UEBhMC
VVMxEzARBgNVBAgMCkNhbGlmb3JuaWExFjAUBgNVBAcMDU1vdW50YWluIFZpZXcx
EDAOBgNVBAoMB0dvb2dsZTEcMBoGA1UEAwwTR29vZ2xlIEhhcmR3YXJlIFJvb3Qw
HhcNMTYwMTEyMDA0MjQ2WhcNMjYwMTEwMDA0MjQ2WjBoMQswCQYDVQQGEwJVUzET
MBEGA1UECAwKQ2FsaWZvcm5pYTEWMBQGA1UEBwwNTW91bnRhaW4gVmlldzEQMA4G
A1UECgwHR29vZ2xlMRwwGgYDVQQDDBNHb29nbGUgSGFyZHdhcmUgUm9vdDBZMBMG
ByqGSM49AgEGCCqGSM49AwEHA0IABH8Z7hA57qI7B549p9yT4W1b7g+XlH/vI7vR
+N/Q82t/pW8i6A6r+5vQ1J4M+wY3q1a5+zV5Z+aZ9O0f9+0E2zmjZjBkMB0GA1Ud
DgQWBBR+pZ1G9qW9a/2r7l2W4Q8+x+x/GjAfBgNVHSMEGDAWgBR+pZ1G9qW9a/2r
7l2W4Q8+x+x/GjASBgNVHRMBAf8ECDAGAQH/AgEAMA4GA1UdDwEB/wQEAwIBBjAK
BggqhkjOPQQDAgNIADBFAiEAs78G0T9W+W8C2k+P5vQ/1G5+B51yK0/P3o2b4/Tz
0HkCIGq/wT7/2B/4w+R6/v1+E4/Xz+zY/YxR/R5/zH/wYvYI
-----END CERTIFICATE-----"""

_hasher = PasswordHasher(
    time_cost=settings.security.ARGON2_TIME_COST,
    memory_cost=settings.security.ARGON2_MEMORY_COST,
    parallelism=settings.security.ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
)

async def hash_password(plain: str) -> str:
    return await run_in_threadpool(_hasher.hash, plain)

async def verify_password(plain: str, hashed: str) -> bool:
    try:
        return await run_in_threadpool(_hasher.verify, hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def generate_session_token() -> str:
    return secrets.token_hex(32)

def generate_provisioning_token() -> str:
    """Generates an 8-character Base32 OTPT (A-Z, 2-7)."""
    token_bytes = secrets.token_bytes(5)
    return base64.b32encode(token_bytes).decode('utf-8')

def extract_public_key_from_cert(cert_b64: str) -> str:
    """Extract the uncompressed secp256r1 public key hex from a Base64-encoded X.509 certificate.

    Strictly expects DER decoding. Raises ValueError on any parsing or curve mismatch.
    """
    try:
        cert_bytes = base64.b64decode(cert_b64)
        cert = x509.load_der_x509_certificate(cert_bytes)
    except Exception as exc:
        raise ValueError(f"Invalid Base64 or DER certificate data: {exc}") from exc

    public_key = cert.public_key()

    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError(
            "Certificate does not contain an Elliptic Curve public key.",
        )

    if not isinstance(public_key.curve, ec.SECP256R1):
        raise ValueError(
            f"Expected SECP256R1 curve, got {public_key.curve.name}.",
        )

    uncompressed_bytes = public_key.public_bytes(
        Encoding.X962,
        PublicFormat.UncompressedPoint,
    )
    return uncompressed_bytes.hex()

def verify_secp256r1_signature(
    public_key_hex: str,
    payload: bytes,
    signature_hex: str,
) -> bool:
    try:
        public_key_bytes = bytes.fromhex(public_key_hex)
        signature_bytes = bytes.fromhex(signature_hex)

        public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(),
            public_key_bytes
        )

        public_key.verify(
            signature_bytes,
            payload,
            ec.ECDSA(hashes.SHA256())
        )
        return True

    except Exception:
        log.error(
            "Signature verification failed: malformed key or signature.",
            exc_info=True,
        )
        return False

def extract_public_key_pem_from_cert(cert_b64: str) -> str:
    try:
        cert_bytes = base64.b64decode(cert_b64)
        cert = x509.load_der_x509_certificate(cert_bytes)
    except Exception as exc:
        raise ValueError("Failed to decode certificate strictly as DER.") from exc
    
    public_key = cert.public_key()
    return public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode('utf-8')

def compute_hardware_fingerprint(cert_b64: str) -> str:
    try:
        cert_bytes = base64.b64decode(cert_b64)
        cert = x509.load_der_x509_certificate(cert_bytes)
    except Exception as exc:
        raise ValueError("Failed to decode certificate strictly as DER.") from exc
    
    public_key = cert.public_key()
    der_bytes = public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der_bytes).hexdigest().lower()

def validate_attestation_chain(certificate_chain: list[str]) -> None:
    if not certificate_chain:
        raise ValueError("Empty certificate chain.")
        
    google_root = x509.load_pem_x509_certificate(GOOGLE_ROOT_CA_PEM.encode())
    
    certs = []
    for cert_b64 in certificate_chain:
        try:
            cert_bytes = base64.b64decode(cert_b64)
            certs.append(x509.load_der_x509_certificate(cert_bytes))
        except Exception as exc:
            raise ValueError("All certificates must be valid DER.") from exc
            
    if certs[-1].public_bytes(Encoding.DER) != google_root.public_bytes(Encoding.DER):
        raise ValueError("Untrusted Root CA: The attestation chain is not rooted in the Google Hardware Attestation Root CA.")

    now = datetime.now(timezone.utc)
    for cert in certs:
        valid_before = getattr(cert, 'not_valid_before_utc', cert.not_valid_before)
        if valid_before.tzinfo is None:
            valid_before = valid_before.replace(tzinfo=timezone.utc)
        valid_after = getattr(cert, 'not_valid_after_utc', cert.not_valid_after)
        if valid_after.tzinfo is None:
            valid_after = valid_after.replace(tzinfo=timezone.utc)
        
        if valid_before > now or valid_after < now:
            raise ValueError("A certificate in the chain is expired or not yet valid.")

    try:
        leaf_constraints = certs[0].extensions.get_extension_for_class(x509.BasicConstraints).value
        if leaf_constraints.ca:
            raise ValueError("Leaf certificate must not be a CA.")
    except x509.ExtensionNotFound:
        pass

    for i in range(1, len(certs)):
        try:
            ca_constraints = certs[i].extensions.get_extension_for_class(x509.BasicConstraints).value
            if not ca_constraints.ca:
                raise ValueError(f"Intermediate certificate at index {i} must be a CA.")
        except x509.ExtensionNotFound:
            raise ValueError(f"Intermediate certificate at index {i} is missing BasicConstraints.")

    for i in range(len(certs) - 1):
        leaf = certs[i]
        issuer = certs[i + 1]
        
        issuer_public_key = issuer.public_key()
        
        try:
            if isinstance(issuer_public_key, rsa.RSAPublicKey):
                issuer_public_key.verify(
                    leaf.signature,
                    leaf.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    leaf.signature_hash_algorithm,
                )
            elif isinstance(issuer_public_key, ec.EllipticCurvePublicKey):
                issuer_public_key.verify(
                    leaf.signature,
                    leaf.tbs_certificate_bytes,
                    ec.ECDSA(leaf.signature_hash_algorithm),
                )
            else:
                raise ValueError("Unsupported public key type.")
        except Exception as exc:
            raise ValueError(f"Signature verification failed for certificate at index {i}.") from exc

def parse_attestation_extension(leaf_cert_b64: str) -> dict[str, Any]:
    try:
        cert_bytes = base64.b64decode(leaf_cert_b64)
        cert = x509.load_der_x509_certificate(cert_bytes)
    except Exception as exc:
        raise ValueError("Leaf certificate must be valid DER.") from exc
        
    ATTESTATION_OID = x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.1.17")
    try:
        ext = cert.extensions.get_extension_for_oid(ATTESTATION_OID)
    except x509.ExtensionNotFound:
        raise ValueError("Attestation extension not found in certificate.")
        
    seq = core.Sequence.load(ext.value.value) # type: ignore
    return {
        "attestationSecurityLevel": seq[1].native, # type: ignore
        "attestationChallenge": seq[4].native, # type: ignore
        "softwareEnforced": seq[6],
        "teeEnforced": seq[7]
    }

def _find_asn1_tag(auth_list: core.Sequence, tag: int) -> Any:
    for item in auth_list:
        if getattr(item, 'tag', None) == tag:
            if hasattr(item, 'parsed'):
                return item.parsed.native
            if hasattr(item, 'native'):
                return item.native
            return item
    return None

def validate_attestation_properties(extension_data: dict[str, Any], provisioning_token: str, package_name: str) -> None:
    sec_level = extension_data.get("attestationSecurityLevel")
    if sec_level not in (1, 2):
        raise ValueError(f"Attestation security level must be TEE (1) or StrongBox (2), got {sec_level}")

    challenge_bytes = extension_data.get("attestationChallenge")
    if not isinstance(challenge_bytes, (bytes, bytearray)):
        raise ValueError("Attestation challenge missing or not bytes.")
    
    try:
        challenge_str = challenge_bytes.decode('utf-8')
    except Exception:
        raise ValueError("Attestation challenge is not valid UTF-8.")
        
    if challenge_str != provisioning_token:
        raise ValueError(f"Attestation challenge mismatch. Expected {provisioning_token}")

    tee_enforced = extension_data.get("teeEnforced")
    if tee_enforced is None:
        raise ValueError("TEE-enforced attestation data missing.")

    auth_timeout = _find_asn1_tag(tee_enforced, 505)
    if auth_timeout is not None:
        raise ValueError("TEE key must require per-operation authentication. authTimeout must be absent.")
        
    origin = _find_asn1_tag(tee_enforced, 702)
    if origin != 0:
        raise ValueError(f"TEE key origin must be 0 (Generated), got {origin}")
        
    purpose = _find_asn1_tag(tee_enforced, 1)
    if not purpose or 2 not in purpose:
        raise ValueError("TEE key purpose must include 2 (Sign)")
    
    user_auth_type = _find_asn1_tag(tee_enforced, 504)
    if user_auth_type != 2:
        raise ValueError(f"TEE key does not strictly mandate biometric authentication. userAuthType: {user_auth_type}")

    root_of_trust_bytes = _find_asn1_tag(tee_enforced, 704)
    if not root_of_trust_bytes:
        raise ValueError("rootOfTrust (704) missing in teeEnforced")
        
    root_of_trust_seq = core.Sequence.load(root_of_trust_bytes)
    if root_of_trust_seq[0].native != 0:
        raise ValueError("verifiedBootState is not Verified (0)")
    if root_of_trust_seq[1].native is not True:
        raise ValueError("deviceLocked is not True")

    software_enforced = extension_data.get("softwareEnforced")
    if software_enforced is None:
        raise ValueError("softwareEnforced attestation data missing.")
    
    app_id_octet_string = _find_asn1_tag(software_enforced, 709)
    if not app_id_octet_string:
        raise ValueError("attestationApplicationId (709) missing in softwareEnforced")
        
    app_id_seq = core.Sequence.load(app_id_octet_string)
    package_infos = app_id_seq[0]
    
    found_package = False
    for pkg_info in package_infos:
        pkg_name_bytes = pkg_info[0].native
        if pkg_name_bytes.decode('utf-8') == package_name:
            found_package = True
            
            if settings.app.ENVIRONMENT == EnvironmentOption.PRODUCTION:
                expected_apk_hash = settings.security.EXPECTED_APK_HASH
                if not expected_apk_hash:
                    raise ValueError("EXPECTED_APK_HASH must be set in production environment.")
                
                if len(pkg_info) > 1 and len(pkg_info[1]) > 0:
                    apk_hash_bytes = pkg_info[1][0].native
                    apk_hash_hex = apk_hash_bytes.hex().lower()
                    if apk_hash_hex != expected_apk_hash.lower():
                        raise ValueError(f"App identity proof failed. APK hash mismatch.")
                else:
                    raise ValueError("App identity proof failed. No APK signature hash found in attestation.")
            break
            
    if not found_package:
        raise ValueError(f"App identity proof failed. Package {package_name} not authorized.")