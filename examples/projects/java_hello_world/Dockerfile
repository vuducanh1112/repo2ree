# Maven on Temurin 17, pinned by its multi-platform digest
FROM maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584

WORKDIR /app
COPY . .

# Build the app and copy dependencies into 'target/dependency'
RUN mvn clean package dependency:copy-dependencies -DskipTests

# Run by pointing the classpath to your classes AND the dependency folder
CMD ["java", "-cp", "target/classes:target/dependency/*", "com.example.Main"]

