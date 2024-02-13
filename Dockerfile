FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ARG PIP_NO_CACHE_DIR=1

# Install Chromium
RUN apt-get -y update
# RUN apt-get install -y chromium-driver
# https://stackoverflow.com/a/47204160

RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN dpkg -i google-chrome-stable_current_amd64.deb --fix-missing; apt-get -fy install


# Upgrade pip, install pipenv
RUN pip install --upgrade pip
RUN pip install pipenv

WORKDIR /usr/src/app

# Copy files that list dependencies
COPY Pipfile.lock Pipfile ./

# Generate requirements.txt and install dependencies from there
RUN pipenv requirements > requirements.txt
RUN pip install -r requirements.txt

# Copy all other files, including source files
COPY . .
