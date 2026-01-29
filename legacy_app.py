import os
import threading
import random
import requests
from datetime import datetime, timedelta

from flask import render_template, request, jsonify, redirect, url_for, flash, send_file, send_from_directory
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Message
from pypdf import PdfReader
import stripe
from apify_client import ApifyClient

from app.extensions import db, mail
from app.models import User, Report, Document
from app.constants import AGENTS_CONFIG, PLAN_LEVELS
from app.workers.heavy_worker import heavy_lifting_worker
from app.workers.video_worker import worker_video_tutorial
