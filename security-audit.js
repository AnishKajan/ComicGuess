#!/usr/bin/env node

/**
 * Security audit script for ComicGuess application
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Security audit results
const auditResults = {
  passed: 0,
  failed: 0,
  warnings: 0,
  issues: []
};

// Helper functions
function addIssue(type, severity, message, file = null) {
  auditResults.issues.push({
    type,
    severity,
    message,
    file,
    timestamp: new Date().toISOString()
  });
  
  if (severity === 'error') {
    auditResults.failed++;
    console.log(`❌ ${type}: ${message}${file ? ` (${file})` : ''}`);
  } else if (severity === 'warning') {
    auditResults.warnings++;
    console.log(`⚠️  ${type}: ${message}${file ? ` (${file})` : ''}`);
  } else {
    auditResults.passed++;
    console.log(`✅ ${type}: ${message}${file ? ` (${file})` : ''}`);
  }
}

function fileExists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch (error) {
    return false;
  }
}

function readFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch (error) {
    return null;
  }
}

function checkFileContent(filePath, patterns, description) {
  const content = readFile(filePath);
  if (!content) {
    addIssue('File Check', 'error', `Cannot read ${description}`, filePath);
    return false;
  }
  
  for (const pattern of patterns) {
    if (pattern.required && !pattern.regex.test(content)) {
      addIssue('Security Check', 'error', `Missing ${pattern.description}`, filePath);
    } else if (!pattern.required && pattern.regex.test(content)) {
      addIssue('Security Check', 'warning', `Found ${pattern.description}`, filePath);
    } else if (pattern.required) {
      addIssue('Security Check', 'info', `Found ${pattern.description}`, filePath);
    }
  }
  
  return true;
}

// Security audit functions
function auditEnvironmentFiles() {
  console.log('\n🔍 Auditing Environment Configuration...');
  
  // Check for example files
  const envFiles = [
    'backend/.env.example',
    'backend/.env.production.example',
    'frontend/.env.example',
    'frontend/.env.local.example'
  ];
  
  envFiles.forEach(file => {
    if (fileExists(file)) {
      addIssue('Environment', 'info', `Environment example file exists`, file);
    } else {
      addIssue('Environment', 'warning', `Missing environment example file`, file);
    }
  });
  
  // Check for actual env files (should not be in repo)
  const actualEnvFiles = [
    'backend/.env',
    'backend/.env.production',
    'frontend/.env.local'
  ];
  
  actualEnvFiles.forEach(file => {
    if (fileExists(file)) {
      addIssue('Environment', 'error', `Environment file should not be in repository`, file);
    } else {
      addIssue('Environment', 'info', `Environment file properly excluded from repository`, file);
    }
  });
}

function auditSecurityHeaders() {
  console.log('\n🛡️ Auditing Security Headers...');
  
  // Check backend security configuration
  const backendMainFile = 'backend/main.py';
  if (fileExists(backendMainFile)) {
    checkFileContent(backendMainFile, [
      {
        regex: /CORSMiddleware/,
        required: true,
        description: 'CORS middleware configuration'
      },
      {
        regex: /allow_origins.*localhost/,
        required: false,
        description: 'localhost in CORS origins (should be production-only)'
      }
    ], 'backend main file');
  }
  
  // Check frontend security configuration
  const nextConfigFile = 'frontend/next.config.ts';
  if (fileExists(nextConfigFile)) {
    checkFileContent(nextConfigFile, [
      {
        regex: /X-Frame-Options/,
        required: true,
        description: 'X-Frame-Options header'
      },
      {
        regex: /X-Content-Type-Options/,
        required: true,
        description: 'X-Content-Type-Options header'
      }
    ], 'Next.js config file');
  }
}

function auditAuthentication() {
  console.log('\n🔐 Auditing Authentication...');
  
  // Check JWT configuration
  const jwtFile = 'backend/app/auth/jwt_handler.py';
  if (fileExists(jwtFile)) {
    checkFileContent(jwtFile, [
      {
        regex: /jwt\.encode/,
        required: true,
        description: 'JWT encoding implementation'
      },
      {
        regex: /jwt\.decode/,
        required: true,
        description: 'JWT decoding implementation'
      },
      {
        regex: /ExpiredSignatureError/,
        required: true,
        description: 'JWT expiration handling'
      }
    ], 'JWT handler');
  }
  
  // Check authentication middleware
  const authMiddlewareFile = 'backend/app/auth/middleware.py';
  if (fileExists(authMiddlewareFile)) {
    checkFileContent(authMiddlewareFile, [
      {
        regex: /get_current_user/,
        required: true,
        description: 'User authentication function'
      },
      {
        regex: /(HTTPException.*401|HTTP_401_UNAUTHORIZED|AuthenticationError)/,
        required: true,
        description: 'Unauthorized error handling'
      }
    ], 'authentication middleware');
  }
}

function auditInputValidation() {
  console.log('\n🔍 Auditing Input Validation...');
  
  // Check backend input validation
  const validationFile = 'backend/app/security/input_validation.py';
  if (fileExists(validationFile)) {
    checkFileContent(validationFile, [
      {
        regex: /sanitize/,
        required: true,
        description: 'Input sanitization functions'
      },
      {
        regex: /validate/,
        required: true,
        description: 'Input validation functions'
      }
    ], 'input validation module');
  }
  
  // Check Pydantic models
  const userModelFile = 'backend/app/models/user.py';
  if (fileExists(userModelFile)) {
    checkFileContent(userModelFile, [
      {
        regex: /BaseModel/,
        required: true,
        description: 'Pydantic BaseModel usage'
      },
      {
        regex: /Field.*min_length/,
        required: true,
        description: 'Field length validation'
      }
    ], 'user model');
  }
}

function auditRateLimiting() {
  console.log('\n⏱️ Auditing Rate Limiting...');
  
  const rateLimitFile = 'backend/app/middleware/rate_limiting.py';
  if (fileExists(rateLimitFile)) {
    checkFileContent(rateLimitFile, [
      {
        regex: /rate_limit/,
        required: true,
        description: 'Rate limiting implementation'
      },
      {
        regex: /429/,
        required: true,
        description: 'Rate limit exceeded response'
      }
    ], 'rate limiting middleware');
  }
}

function auditSecrets() {
  console.log('\n🔑 Auditing Secrets Management...');
  
  // Check for hardcoded secrets
  const filesToCheck = [
    'backend/main.py',
    'backend/app/config/settings.py',
    'frontend/src/lib/api-client.ts'
  ];
  
  const secretPatterns = [
    /password\s*=\s*["'][^"']+["']/i,
    /secret\s*=\s*["'][^"']+["']/i,
    /key\s*=\s*["'][^"']+["']/i,
    /token\s*=\s*["'][^"']+["']/i
  ];
  
  filesToCheck.forEach(file => {
    if (fileExists(file)) {
      const content = readFile(file);
      if (content) {
        secretPatterns.forEach(pattern => {
          if (pattern.test(content)) {
            addIssue('Secrets', 'warning', 'Potential hardcoded secret found', file);
          }
        });
      }
    }
  });
}

function auditDependencies() {
  console.log('\n📦 Auditing Dependencies...');
  
  // Check for package files
  const packageFiles = [
    'backend/requirements.txt',
    'frontend/package.json'
  ];
  
  packageFiles.forEach(file => {
    if (fileExists(file)) {
      addIssue('Dependencies', 'info', `Package file exists`, file);
      
      // Check for known vulnerable packages (simplified check)
      const content = readFile(file);
      if (content) {
        // This is a simplified check - in production, use tools like npm audit or safety
        if (content.includes('django<2.0') || content.includes('flask<1.0')) {
          addIssue('Dependencies', 'error', 'Potentially vulnerable dependency version', file);
        }
      }
    } else {
      addIssue('Dependencies', 'error', `Missing package file`, file);
    }
  });
}

function auditLogging() {
  console.log('\n📝 Auditing Logging Configuration...');
  
  const loggingFiles = [
    'backend/app/monitoring/logging_config.py',
    'backend/app/monitoring/error_tracking.py'
  ];
  
  loggingFiles.forEach(file => {
    if (fileExists(file)) {
      checkFileContent(file, [
        {
          regex: /logging/,
          required: true,
          description: 'Logging configuration'
        },
        {
          regex: /ERROR|WARN|INFO/,
          required: true,
          description: 'Log level configuration'
        }
      ], 'logging configuration');
    }
  });
}

function auditDocumentation() {
  console.log('\n📚 Auditing Security Documentation...');
  
  const docFiles = [
    'backend/DEPLOYMENT.md',
    'frontend/DEPLOYMENT.md',
    'PRODUCTION_DEPLOYMENT_CHECKLIST.md'
  ];
  
  docFiles.forEach(file => {
    if (fileExists(file)) {
      addIssue('Documentation', 'info', `Documentation file exists`, file);
    } else {
      addIssue('Documentation', 'warning', `Missing documentation file`, file);
    }
  });
}

function generateReport() {
  console.log('\n📊 Security Audit Report');
  console.log('========================');
  console.log(`✅ Passed: ${auditResults.passed}`);
  console.log(`⚠️  Warnings: ${auditResults.warnings}`);
  console.log(`❌ Failed: ${auditResults.failed}`);
  console.log(`📈 Total Checks: ${auditResults.passed + auditResults.warnings + auditResults.failed}`);
  
  if (auditResults.failed > 0) {
    console.log('\n❌ Critical Issues Found:');
    auditResults.issues
      .filter(issue => issue.severity === 'error')
      .forEach(issue => {
        console.log(`  - ${issue.type}: ${issue.message}${issue.file ? ` (${issue.file})` : ''}`);
      });
  }
  
  if (auditResults.warnings > 0) {
    console.log('\n⚠️  Warnings:');
    auditResults.issues
      .filter(issue => issue.severity === 'warning')
      .forEach(issue => {
        console.log(`  - ${issue.type}: ${issue.message}${issue.file ? ` (${issue.file})` : ''}`);
      });
  }
  
  // Write detailed report to file
  const reportData = {
    timestamp: new Date().toISOString(),
    summary: {
      passed: auditResults.passed,
      warnings: auditResults.warnings,
      failed: auditResults.failed,
      total: auditResults.passed + auditResults.warnings + auditResults.failed
    },
    issues: auditResults.issues
  };
  
  fs.writeFileSync('security-audit-report.json', JSON.stringify(reportData, null, 2));
  console.log('\n📄 Detailed report saved to: security-audit-report.json');
  
  // Return exit code based on results
  return auditResults.failed > 0 ? 1 : 0;
}

// Main audit function
async function runSecurityAudit() {
  console.log('🔒 ComicGuess Security Audit');
  console.log('============================');
  
  auditEnvironmentFiles();
  auditSecurityHeaders();
  auditAuthentication();
  auditInputValidation();
  auditRateLimiting();
  auditSecrets();
  auditDependencies();
  auditLogging();
  auditDocumentation();
  
  const exitCode = generateReport();
  
  console.log('\n🎯 Recommendations:');
  console.log('1. Review and fix all critical issues before production deployment');
  console.log('2. Address warnings to improve security posture');
  console.log('3. Run automated security scans regularly');
  console.log('4. Keep dependencies up to date');
  console.log('5. Monitor security alerts and logs');
  
  process.exit(exitCode);
}

// Run the audit
runSecurityAudit().catch(error => {
  console.error('💥 Security audit failed:', error);
  process.exit(1);
});