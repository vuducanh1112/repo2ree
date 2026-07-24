FROM maven:3.9-eclipse-temurin-17

WORKDIR /app
COPY . .

# Build the app and copy dependencies into 'target/dependency'
RUN mvn clean package dependency:copy-dependencies -DskipTests

# Run by pointing the classpath to your classes AND the dependency folder
CMD ["java", "-cp", "target/classes:target/dependency/*", "com.example.Main"]

