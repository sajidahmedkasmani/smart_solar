# app/utils/helpers.py
import re
from app.models import User # Ya aapka User model path

def unique_username(base_name):
    """
    Base name se clean, unique username generate karta hai.
    """
    clean_name = re.sub(r'[^a-zA-Z0-0]', '', base_name.lower())
    username = clean_name
    counter = 1
    
    while User.query.filter_by(username=username).first():
        username = f"{clean_name}{counter}"
        counter += 1
        
    return username