pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    environment {
        COMPOSE_PROJECT_NAME = "aic2026-ci-${BUILD_NUMBER}"
        BACKEND_PORT = '15000'
        FRONTEND_PORT = '18088'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare environment') {
            steps {
                sh 'cp .env.example .env'
            }
        }

        stage('Backend tests') {
            steps {
                sh '''
                    docker build \
                        --target test \
                        --tag aic2026-backend-test:${BUILD_NUMBER} \
                        ./backendAIC2025

                    docker run --rm \
                        aic2026-backend-test:${BUILD_NUMBER}
                '''
            }
        }

        stage('Frontend lint') {
            steps {
                sh '''
                    docker build \
                        --target test \
                        --tag aic2026-frontend-test:${BUILD_NUMBER} \
                        ./frontend-final/vite-project
                '''
            }
        }

        stage('Validate Compose') {
            steps {
                sh 'docker compose config --quiet'
            }
        }

        stage('Build images') {
            steps {
                sh 'docker compose build'
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
                        wget -qO- http://127.0.0.1/api/health/app
                '''
            }
        }
    }

    post {
        always {
            sh '''
                docker compose logs --no-color --tail=200 || true
                docker compose down --remove-orphans --rmi local || true

                docker image rm \
                    aic2026-backend-test:${BUILD_NUMBER} \
                    aic2026-frontend-test:${BUILD_NUMBER} \
                    2>/dev/null || true
            '''
        }
    }
}