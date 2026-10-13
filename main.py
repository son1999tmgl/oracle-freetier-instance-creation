#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oracle Cloud Infrastructure (OCI) Always-Free Instance Hunter
Chuyen dung san VPS ARM Ampere VM.Standard.A1.Flex tai Tokyo (ap-tokyo-1)
Chay ben bi 24/7 tren Koyeb Worker hoac Local Machine.
"""

import configparser
import datetime
import itertools
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Union

try:
    import oci
except ImportError:
    print("[LOI] Chua cai dat thu vien 'oci'. Hay chay: pip install -r requirements.txt")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

from dotenv import load_dotenv

# Load bien moi truong tu oci.env neu co
load_dotenv('oci.env')

# Setup Logging dong thoi ra Console (cho Koyeb) va file log
# Äáº£m báº£o StreamHandler há»— trá»£ UTF-8 cáº£ trÃªn Windows console vÃ  Linux/Koyeb
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("launch_instance.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("OCI_Hunter")

# -------------------------------------------------------------
# 1. CAC THAM SO CAU HINH
# -------------------------------------------------------------
ARM_SHAPE = "VM.Standard.A1.Flex"
E2_MICRO_SHAPE = "VM.Standard.E2.1.Micro"

DISPLAY_NAME = os.getenv("DISPLAY_NAME", "Tokyo-ARM-AlwaysFree").strip()
OCT_FREE_AD = os.getenv("OCT_FREE_AD", "AD-1").strip()
OCI_COMPUTE_SHAPE = os.getenv("OCI_COMPUTE_SHAPE", ARM_SHAPE).strip()
OCPUS = int(os.getenv("OCPUS", "4").strip())
RAM_IN_GBS = int(os.getenv("RAM_IN_GBS", "24").strip())
BOOT_VOLUME_SIZE = max(50, int(os.getenv("BOOT_VOLUME_SIZE", "200").strip()))
REQUEST_WAIT_TIME_SECS = max(30, int(os.getenv("REQUEST_WAIT_TIME_SECS", "50").strip()))

OPERATING_SYSTEM = os.getenv("OPERATING_SYSTEM", "Canonical Ubuntu").strip()
OS_VERSION = os.getenv("OS_VERSION", "22.04 Minimal aarch64").strip()
ASSIGN_PUBLIC_IP = os.getenv("ASSIGN_PUBLIC_IP", "true").strip().lower() in ["true", "1", "yes"]
OCI_SUBNET_ID = os.getenv("OCI_SUBNET_ID", "").strip() or None
OCI_IMAGE_ID = os.getenv("OCI_IMAGE_ID", "").strip() or None
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()
SSH_AUTHORIZED_KEYS_FILE = os.getenv("SSH_AUTHORIZED_KEYS_FILE", "./id_rsa.pub").strip()

# Credentials qua Env (cho Koyeb Secrets) hoac qua File
OCI_CONFIG_FILE = os.getenv("OCI_CONFIG", "./oci_config").strip()
OCI_KEY_CONTENT = os.getenv("OCI_KEY_CONTENT", "").strip()
SSH_KEY_CONTENT = os.getenv("SSH_AUTHORIZED_KEY_CONTENT", "").strip()

def initialize_oci_config() -> dict:
    """Khoi tao dictionary cau hinh OCI cho SDK"""
    # 1. Truong hop truyen truc tiep Key qua ENV (Deploy tren Koyeb)
    if OCI_KEY_CONTENT:
        key_target_path = Path("/tmp/oci_api_private_key.pem") if os.name != 'nt' else Path("./oci_api_private_key.pem")
        key_target_path.write_text(OCI_KEY_CONTENT.replace("\\n", "\n"), encoding="utf-8")
        try:
            os.chmod(str(key_target_path), 0o600)
        except Exception:
            pass
        logger.info(f"Da tao khoa OCI Private Key tu bien moi truong tai {key_target_path}")

        if os.getenv("OCI_USER_ID") and os.getenv("OCI_TENANCY_ID") and os.getenv("OCI_FINGERPRINT"):
            return {
                "user": os.getenv("OCI_USER_ID").strip(),
                "fingerprint": os.getenv("OCI_FINGERPRINT").strip(),
                "tenancy": os.getenv("OCI_TENANCY_ID").strip(),
                "region": os.getenv("OCI_REGION", "ap-tokyo-1").strip(),
                "key_file": str(key_target_path.resolve())
            }

    # 2. Truong hop doc tu file oci_config
    if not os.path.exists(OCI_CONFIG_FILE):
        logger.error(f"[LOI] Khong tim thay file cau hinh OCI tai: {OCI_CONFIG_FILE}")
        logger.info("-> Vui long tao file oci_config hoac thiet lap bien moi truong OCI_KEY_CONTENT, OCI_USER_ID...")
        sys.exit(1)

    parser = configparser.ConfigParser()
    parser.read(OCI_CONFIG_FILE)
    if "DEFAULT" not in parser:
        logger.error("[LOI] File oci_config thieu section [DEFAULT]")
        sys.exit(1)

    cfg = dict(parser["DEFAULT"])
    raw_key_path = cfg.get("key_file", "")
    if not os.path.isabs(raw_key_path):
        base_dir = Path(OCI_CONFIG_FILE).resolve().parent
        cfg["key_file"] = str((base_dir / raw_key_path).resolve())

    if not os.path.exists(cfg["key_file"]):
        logger.error(f"[LOI] Khong tim thay file khoa Private Key tai: {cfg['key_file']}")
        sys.exit(1)

    return cfg

oci_config_dict = initialize_oci_config()

# Khoi tao OCI Clients
try:
    oci.config.validate_config(oci_config_dict)
    iam_client = oci.identity.IdentityClient(oci_config_dict)
    network_client = oci.core.VirtualNetworkClient(oci_config_dict)
    compute_client = oci.core.ComputeClient(oci_config_dict)
    logger.info(f"[OK] Khoi tao OCI Client thanh cong cho Region: {oci_config_dict['region']}")
except Exception as e:
    logger.error(f"[LOI] Xac thuc cau hinh OCI that bai: {e}")
    sys.exit(1)

# -------------------------------------------------------------
# 2. CAC HAM TIEN ICH
# -------------------------------------------------------------
def send_notification(msg: str):
    """Gui thong bao toi Discord Webhook"""
    if DISCORD_WEBHOOK and requests:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
        except Exception as ex:
            logger.warning(f"Khong the gui thong bao Discord: {ex}")

def get_ssh_public_key() -> str:
    """Lay SSH Public Key de inject vao VPS"""
    if SSH_KEY_CONTENT:
        return SSH_KEY_CONTENT.strip()

    pub_path = Path(SSH_AUTHORIZED_KEYS_FILE)
    if pub_path.exists():
        return pub_path.read_text(encoding="utf-8").strip()

    logger.info(f"Khong tim thay {SSH_AUTHORIZED_KEYS_FILE}, dang tu dong sinh SSH keypair RSA 2048...")
    import paramiko
    key = paramiko.RSAKey.generate(2048)
    priv_path = pub_path.with_name("id_rsa")
    key.write_private_key_file(str(priv_path))
    pub_key_str = f"ssh-rsa {key.get_base64()} oci-arm-key"
    pub_path.write_text(pub_key_str, encoding="utf-8")
    logger.info(f"[OK] Da luu Private Key tai '{priv_path}' va Public Key tai '{pub_path}'")
    return pub_key_str

def get_target_image_id(compartment_id: str) -> str:
    """Tim kiem Image ID phu hop Ubuntu ARM trong Region"""
    if OCI_IMAGE_ID:
        return OCI_IMAGE_ID

    logger.info(f"Dang truy van Image ID cho {OPERATING_SYSTEM} ({OS_VERSION}) tren {OCI_COMPUTE_SHAPE}...")
    images = compute_client.list_images(
        compartment_id=compartment_id,
        shape=OCI_COMPUTE_SHAPE,
        sort_by="TIMECREATED",
        sort_order="DESC"
    ).data

    # Tim chinh xac theo he dieu hanh va phien ban
    for img in images:
        if OPERATING_SYSTEM.lower() in img.operating_system.lower():
            if not OS_VERSION or OS_VERSION.lower() in img.display_name.lower():
                logger.info(f"-> Chon Image: {img.display_name} (ID: {img.id})")
                return img.id

    # Fallback tim Ubuntu bat ky tuong thich ARM
    for img in images:
        if "ubuntu" in img.display_name.lower():
            logger.info(f"-> Fallback chon Image: {img.display_name} (ID: {img.id})")
            return img.id

    if images:
        return images[0].id
    raise RuntimeError("Khong tim thay Image tuong thich ARM nao trong Compartment.")

def check_existing_instance(compartment_id: str) -> bool:
    """Kiem tra xem may ao ARM da duoc tao va dang hoat dong chua"""
    instances = compute_client.list_instances(compartment_id=compartment_id).data
    for inst in instances:
        if inst.shape == OCI_COMPUTE_SHAPE and inst.lifecycle_state in ["PROVISIONING", "RUNNING"]:
            logger.info(f"[DA CO SAN] Phat hien VPS {OCI_COMPUTE_SHAPE} dang chay: {inst.display_name} ({inst.id})")
            return True
    return False

# -------------------------------------------------------------
# 3. TIEN TRINH SAN VPS TU DONG
# -------------------------------------------------------------
def run_hunter():
    tenancy_id = oci_config_dict["tenancy"]

    # 1. Kiem tra xem may ao da tao chua
    if check_existing_instance(tenancy_id):
        logger.info("[HOAN TAT] VPS ARM da ton tai trong tai khoan. Dung chuong trinh de tranh tao trung.")
        return

    # 2. Lay Availability Domains
    ad_list = iam_client.list_availability_domains(compartment_id=tenancy_id).data
    target_ads = [ad.name for ad in ad_list if any(ad.name.lower().endswith(tgt.lower()) for tgt in OCT_FREE_AD.split(","))]
    if not target_ads:
        target_ads = [ad.name for ad in ad_list]
    logger.info(f"Availability Domains muc tieu: {target_ads}")

    # 3. Lay Subnet ID
    subnet_id = OCI_SUBNET_ID
    if not subnet_id:
        subnets = network_client.list_subnets(compartment_id=tenancy_id).data
        if not subnets:
            raise RuntimeError("Khong tim thay Subnet nao trong VCN! Vui long tao VCN va Subnet tren OCI Console truoc.")
        subnet_id = subnets[0].id
    logger.info(f"Su dung Subnet ID: {subnet_id}")

    # 4. Lay Image ID va SSH Key
    image_id = get_target_image_id(tenancy_id)
    ssh_key = get_ssh_public_key()

    # 5. Cau hinh Shape ARM
    if OCI_COMPUTE_SHAPE == ARM_SHAPE:
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=float(OCPUS),
            memory_in_gbs=float(RAM_IN_GBS)
        )
    else:
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=1.0, memory_in_gbs=1.0)

    ad_cycle = itertools.cycle(target_ads)
    attempt = 1
    send_notification(f"ðŸš€ [OCI Hunter] Bat dau san VPS ARM tai Tokyo ({OCPUS} OCPU / {RAM_IN_GBS}GB RAM) 24/7!")

    logger.info("==================================================================")
    logger.info("BAT DAU VONG LAP SAN VPS ORACLE CLOUD ARM (ALWAY FREE)")
    logger.info(f"Target: {OCI_COMPUTE_SHAPE} | {OCPUS} OCPUs | {RAM_IN_GBS} GB RAM | {BOOT_VOLUME_SIZE} GB Disk")
    logger.info(f"Interval: ~{REQUEST_WAIT_TIME_SECS}s giua cac lan thu")
    logger.info("==================================================================")

    while True:
        current_ad = next(ad_cycle)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[Thu lan #{attempt} | {now_str}] Gui request tao VPS tai '{current_ad}'...")

        launch_details = oci.core.models.LaunchInstanceDetails(
            availability_domain=current_ad,
            compartment_id=tenancy_id,
            display_name=DISPLAY_NAME,
            shape=OCI_COMPUTE_SHAPE,
            shape_config=shape_config,
            create_vnic_details=oci.core.models.CreateVnicDetails(
                assign_public_ip=ASSIGN_PUBLIC_IP,
                assign_private_dns_record=True,
                display_name=DISPLAY_NAME,
                subnet_id=subnet_id
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=image_id,
                boot_volume_size_in_gbs=BOOT_VOLUME_SIZE
            ),
            metadata={"ssh_authorized_keys": ssh_key}
        )

        try:
            response = compute_client.launch_instance(launch_instance_details=launch_details)
            if response.status in [200, 201]:
                inst = response.data
                success_msg = (
                    f"ðŸŽ‰ðŸŽ‰ [THANH CONG] DA SAN DUOC VPS ORACLE ARM!\n"
                    f"- Instance ID: {inst.id}\n"
                    f"- Display Name: {inst.display_name}\n"
                    f"- Availability Domain: {inst.availability_domain}\n"
                    f"- Cau hinh: {OCPUS} OCPU | {RAM_IN_GBS} GB RAM | {BOOT_VOLUME_SIZE} GB Storage\n"
                    f"- Thoi gian: {now_str}"
                )
                logger.info(success_msg)
                send_notification(success_msg)
                with open("INSTANCE_CREATED", "w", encoding="utf-8") as f:
                    f.write(success_msg)
                logger.info("Ket thuc tien trinh thanh cong. Dung vong lap.")
                sys.exit(0)

        except oci.exceptions.ServiceError as srv_err:
            status = srv_err.status
            code = srv_err.code
            msg = srv_err.message

            if status in [500, 429, 502, 503, 504] or "capacity" in msg.lower() or code == "TooManyRequests":
                logger.warning(f"âš ï¸ [Het Slot / Rate Limit] Code: {code} (HTTP {status}) - {msg.strip()}")
            elif code == "LimitExceeded":
                logger.warning(f"âš ï¸ [LimitExceeded]: Phat hien gioi han tai nguyen. Dang kiem tra xem VPS da tao chua...")
                if check_existing_instance(tenancy_id):
                    logger.info("[THANH CONG] Phat hien VPS da duoc khoi tao thanh cong! Ket thuc script.")
                    sys.exit(0)
            else:
                logger.error(f"âŒ [Loi OCI API] Code: {code} | Status: {status} | Msg: {msg}")

        except (oci.exceptions.RequestException, Exception) as general_err:
            logger.warning(f"âš ï¸ [Loi ket noi mang / Timeout tam thoi]: {general_err}")

        # Thoi gian nghi kem Jitter ngau nhien
        sleep_secs = REQUEST_WAIT_TIME_SECS + random.randint(1, 6)
        logger.info(f"â³ Nghi {sleep_secs} giay truoc lan thu tiep theo...\n")
        time.sleep(sleep_secs)
        attempt += 1

# =============================================================
# DUMMY HTTP SERVER CHO RENDER WEB SERVICE (PORT HEALTH CHECK)
# =============================================================
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'OCI Instance Hunter is Running 24/7 on Render!')

    def log_message(self, format, *args):
        pass

def run_background_http_server():
    port = int(os.getenv("PORT", "10000"))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"[HEALTH CHECK] HTTP Server da mo tai cong {port} cho Render.")
    except Exception as e:
        logger.warning(f"Khong the mo HTTP port {port}: {e}")

if __name__ == "__main__":
    run_background_http_server()
    try:
        run_hunter()
    except KeyboardInterrupt:
        logger.info("[DUNG] Nguoi dung chu dong ngat tien trinh (Ctrl+C).")
        sys.exit(0)
    except Exception as fatal:
        logger.critical(f"[LOI FATAL]: {fatal}", exc_info=True)
        send_notification(f"âŒ [OCI Hunter] Script bi dung do loi: {fatal}")
        sys.exit(1)

