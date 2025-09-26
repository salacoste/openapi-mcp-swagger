# Sample Swagger Files

This directory contains real-world Swagger/OpenAPI examples that you can use to test and explore the swagger-mcp-server functionality.

## Available Examples

### 📱 E-commerce API (`ecommerce-api.json`)
A comprehensive e-commerce platform API featuring:
- **Product Management**: CRUD operations for products, categories, inventory
- **User Management**: Authentication, profiles, preferences
- **Order Processing**: Shopping cart, checkout, order tracking
- **Payment Integration**: Multiple payment methods, webhooks
- **Review System**: Product reviews, ratings, moderation

**Complexity**: Medium
**Endpoints**: 45
**Schemas**: 23
**Use Cases**: Online stores, marketplace platforms, retail systems

### 🏦 Banking API (`banking-api.json`)
A secure banking and financial services API including:
- **Account Management**: Account creation, balance inquiries, statements
- **Transaction Processing**: Transfers, payments, transaction history
- **Card Services**: Card management, activation, blocking
- **Loan Services**: Application, approval, payment tracking
- **Security Features**: Multi-factor authentication, fraud detection

**Complexity**: High
**Endpoints**: 67
**Schemas**: 34
**Use Cases**: Financial applications, fintech platforms, banking systems

### 🏥 Healthcare API (`healthcare-api.json`)
A HIPAA-compliant healthcare management API featuring:
- **Patient Management**: Records, appointments, medical history
- **Provider Services**: Doctor profiles, availability, specializations
- **Appointment System**: Scheduling, reminders, cancellations
- **Medical Records**: Secure document storage, sharing
- **Billing Integration**: Insurance, claims, payment processing

**Complexity**: High
**Endpoints**: 52
**Schemas**: 31
**Use Cases**: Hospital systems, clinic management, telemedicine

### 📱 Social Media API (`social-api.json`)
A modern social networking platform API including:
- **User Profiles**: Registration, profiles, privacy settings
- **Content Management**: Posts, media uploads, content moderation
- **Social Features**: Friends, followers, messaging
- **Feed Algorithm**: Timeline, recommendations, trending content
- **Analytics**: User engagement, content performance

**Complexity**: Medium-High
**Endpoints**: 38
**Schemas**: 19
**Use Cases**: Social platforms, community apps, content management

### 🏢 Enterprise CRM (`enterprise-crm.json`)
A comprehensive Customer Relationship Management API featuring:
- **Contact Management**: Leads, customers, organizations
- **Sales Pipeline**: Opportunities, deals, forecasting
- **Marketing Automation**: Campaigns, email marketing, analytics
- **Support Ticketing**: Cases, knowledge base, escalations
- **Reporting**: Custom reports, dashboards, KPIs

**Complexity**: Very High
**Endpoints**: 89
**Schemas**: 47
**Use Cases**: Enterprise software, CRM systems, business applications

### 🌐 IoT Platform (`iot-platform.json`)
An Internet of Things device management API including:
- **Device Management**: Registration, configuration, monitoring
- **Data Collection**: Sensor readings, telemetry, time-series data
- **Remote Control**: Commands, firmware updates, diagnostics
- **Analytics**: Data processing, alerts, visualization
- **Security**: Device authentication, encryption, access control

**Complexity**: Medium
**Endpoints**: 31
**Schemas**: 16
**Use Cases**: IoT platforms, smart homes, industrial monitoring

## Quick Start with Examples

### Generate Sample Files
```bash
# Create a specific example
swagger-mcp-server examples create-sample --type ecommerce --output ./ecommerce-api.json

# List all available examples
swagger-mcp-server examples list
```

### Convert and Test
```bash
# Convert sample to MCP server
swagger-mcp-server convert ecommerce-api.json --name ecommerce-demo

# Start the server
cd mcp-server-ecommerce-demo
swagger-mcp-server serve

# Test with sample queries
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "searchEndpoints",
    "params": {"keywords": "product search"}
  }'
```

## Example Use Cases by Industry

### E-commerce & Retail
- **Product Catalog Management**: Search products, manage inventory
- **Customer Experience**: User accounts, order tracking, reviews
- **Payment Processing**: Multiple payment methods, refunds, billing

### Financial Services
- **Account Operations**: Balance inquiries, transaction history
- **Payment Systems**: Transfers, bill payments, recurring payments
- **Compliance**: Audit trails, reporting, regulatory requirements

### Healthcare
- **Patient Care**: Appointment scheduling, medical records access
- **Provider Management**: Doctor availability, specialization lookup
- **Billing & Insurance**: Claims processing, payment tracking

### Technology & SaaS
- **User Management**: Authentication, authorization, user profiles
- **API Integration**: Webhooks, third-party connectors, data sync
- **Analytics**: Usage metrics, performance monitoring, reporting

## Testing Scenarios

### Basic Functionality Tests
```bash
# Test endpoint search
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"user"}}'

# Test schema retrieval
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":2,"method":"getSchema","params":{"componentName":"User"}}'

# Test example generation
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":3,"method":"getExample","params":{"endpointId":"createUser","language":"curl"}}'
```

### Advanced Search Tests
```bash
# Search by HTTP method
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"httpMethods":["POST","PUT"]}}'

# Search with filters
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"payment","tags":["billing"],"deprecated":false}}'

# Complex search query
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"user authentication","httpMethods":["POST"],"maxResults":5}}'
```

### Performance Tests
```bash
# Concurrent requests test
for i in {1..10}; do
  curl -X POST http://localhost:8080 \
    -d '{"jsonrpc":"2.0","id":'$i',"method":"searchEndpoints","params":{"keywords":"test"}}' &
done
wait

# Large result set test
curl -X POST http://localhost:8080 \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"","maxResults":100}}'
```

## API Complexity Comparison

| Example | Endpoints | Schemas | Complexity | Best For |
|---------|-----------|---------|------------|----------|
| E-commerce | 45 | 23 | Medium | Learning, demos |
| Banking | 67 | 34 | High | Security testing |
| Healthcare | 52 | 31 | High | Compliance scenarios |
| Social Media | 38 | 19 | Medium-High | Real-time features |
| Enterprise CRM | 89 | 47 | Very High | Scale testing |
| IoT Platform | 31 | 16 | Medium | Device integration |

## Custom Example Creation

### Adding Your Own Examples
1. Create a valid OpenAPI 3.0+ JSON file
2. Place it in this directory
3. Update this README with description
4. Test conversion and functionality

### Example Template
```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "Your API Name",
    "version": "1.0.0",
    "description": "Description of your API"
  },
  "servers": [
    {
      "url": "https://api.example.com/v1",
      "description": "Production server"
    }
  ],
  "paths": {
    "/example": {
      "get": {
        "summary": "Example endpoint",
        "operationId": "getExample",
        "responses": {
          "200": {
            "description": "Success response"
          }
        }
      }
    }
  }
}
```

## Validation and Quality

All example files are:
- ✅ **OpenAPI 3.0+ compliant**: Validated against official specification
- ✅ **Realistic**: Based on real-world API patterns and requirements
- ✅ **Complete**: Include comprehensive schemas, examples, and documentation
- ✅ **Tested**: Verified to work correctly with swagger-mcp-server
- ✅ **Documented**: Each endpoint and schema includes meaningful descriptions

## Contributing Examples

Want to contribute a new example? Please:
1. Ensure OpenAPI 3.0+ compliance
2. Include realistic, complete schemas
3. Add meaningful descriptions and examples
4. Test with swagger-mcp-server
5. Update this README
6. Submit a pull request

**Popular requests:**
- Government/Public API examples
- Real estate and property management
- Education and learning management
- Travel and hospitality
- Supply chain and logistics