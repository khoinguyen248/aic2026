pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        COMPOSE_PROJECT_NAME = "aic2026-ci"
        BACKEND_PORT = "15000"
        FRONTEND_PORT = "18088"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare environment') {
            steps {
                sh '''
                    cp .env.example .env
                '''
            }
        }

        stage('Validate Compose') {
            steps {
                sh '''
                    docker compose config --quiet
                '''
            }
        }

        stage('Build images') {
            steps {
                sh '''
                    docker compose build
                '''
            }
        }

        stage('Start services') {
            steps {
                sh '''
                    docker compose up -d --wait --wait-timeout 120
                    docker compose ps
                '''
            }
        }

        stage('Smoke test') {
            steps {
                sh '''
                    docker compose exec -T frontend \
                        wget -qO- http://localhost/api/health/app
                '''
            }
        }
    }

    post {
        always {
            sh '''
                docker compose logs --no-color --tail=200 || true
                docker compose down --remove-orphans || true
            '''
        }
    }
}