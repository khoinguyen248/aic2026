pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    environment {
        COMPOSE_PROJECT_NAME = "aic2026-ci-${BUILD_NUMBER}"
        PRODUCTION_PROJECT = 'aic2026-production'

        BACKEND_PORT = '15000'
        FRONTEND_PORT = '18088'
        PRODUCTION_FRONTEND_PORT = '8088'

        REGISTRY = 'ghcr.io'
        BACKEND_IMAGE = 'ghcr.io/khoinguyen248/aic2026-backend'
        FRONTEND_IMAGE = 'ghcr.io/khoinguyen248/aic2026-frontend'
        IMAGE_TAG = "${BUILD_NUMBER}"
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
                        --tag "aic2026-backend-test:${BUILD_NUMBER}" \
                        ./backendAIC2025

                    docker run --rm \
                        "aic2026-backend-test:${BUILD_NUMBER}"
                '''
            }
        }

        stage('Frontend lint') {
            steps {
                sh '''
                    docker build \
                        --target test \
                        --tag "aic2026-frontend-test:${BUILD_NUMBER}" \
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
                    docker compose up -d \
                        --wait \
                        --wait-timeout 120

                    docker compose ps
                '''
            }
        }

        stage('Smoke test') {
            steps {
                sh '''
                    docker compose exec -T frontend \
                        wget -qO- \
                        http://127.0.0.1/api/health/app
                '''
            }
        }

        stage('Publish images') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'ghcr-credentials',
                        usernameVariable: 'GHCR_USERNAME',
                        passwordVariable: 'GHCR_TOKEN'
                    )
                ]) {
                    sh '''
                        echo "$GHCR_TOKEN" |
                            docker login "$REGISTRY" \
                                --username "$GHCR_USERNAME" \
                                --password-stdin

                        docker push \
                            "$BACKEND_IMAGE:$IMAGE_TAG"

                        docker push \
                            "$FRONTEND_IMAGE:$IMAGE_TAG"

                        docker tag \
                            "$BACKEND_IMAGE:$IMAGE_TAG" \
                            "$BACKEND_IMAGE:latest"

                        docker tag \
                            "$FRONTEND_IMAGE:$IMAGE_TAG" \
                            "$FRONTEND_IMAGE:latest"

                        docker push \
                            "$BACKEND_IMAGE:latest"

                        docker push \
                            "$FRONTEND_IMAGE:latest"

                        docker logout "$REGISTRY"
                    '''
                }
            }
        }

        stage('Deploy production') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'ghcr-credentials',
                        usernameVariable: 'GHCR_USERNAME',
                        passwordVariable: 'GHCR_TOKEN'
                    ),
                    file(
                        credentialsId: 'aic-production-env',
                        variable: 'PRODUCTION_ENV_FILE'
                    )
                ]) {
                    sh '''
                        echo "$GHCR_TOKEN" |
                            docker login "$REGISTRY" \
                                --username "$GHCR_USERNAME" \
                                --password-stdin

                        docker compose \
                            --project-name "$PRODUCTION_PROJECT" \
                            --file compose.production.yaml \
                            pull

                        docker compose \
                            --project-name "$PRODUCTION_PROJECT" \
                            --file compose.production.yaml \
                            up -d \
                            --remove-orphans \
                            --wait \
                            --wait-timeout 120

                        docker compose \
                            --project-name "$PRODUCTION_PROJECT" \
                            --file compose.production.yaml \
                            ps

                        docker compose \
                            --project-name "$PRODUCTION_PROJECT" \
                            --file compose.production.yaml \
                            exec -T frontend \
                            wget -qO- \
                            http://127.0.0.1/api/health/app

                        docker logout "$REGISTRY"
                    '''
                }
            }
        }
    }

    post {
        always {
            sh '''
                docker compose logs \
                    --no-color \
                    --tail=200 || true

                docker compose down \
                    --remove-orphans || true

                docker image rm \
                    "aic2026-backend-test:${BUILD_NUMBER}" \
                    "aic2026-frontend-test:${BUILD_NUMBER}" \
                    "$BACKEND_IMAGE:$IMAGE_TAG" \
                    "$FRONTEND_IMAGE:$IMAGE_TAG" \
                    "$BACKEND_IMAGE:latest" \
                    "$FRONTEND_IMAGE:latest" \
                    2>/dev/null || true
            '''
        }
    }
}