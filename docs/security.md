# CodeMentor-RAG Security

## Threat Model

CodeMentor-RAG processes untrusted repository input. Imported repositories may contain malicious content designed to exploit the analysis system.

## Security Measures

### ZIP Archive Security

**Zip Slip Prevention:**
- All archive paths are validated before extraction
- Absolute paths are rejected
- Path components containing `..` are rejected
- Resolved paths must remain within the target extraction directory
- Symlinks in archives are rejected

**Decompression Bomb Protection:**
- Maximum extracted size enforced (`MAX_EXTRACTED_MB`, default 2000MB)
- Maximum file count enforced (`MAX_REPOSITORY_FILES`, default 10000)
- Individual file size limits (`MAX_FILE_MB`, default 10MB)

### Git Clone Security

- Git URLs are validated (must use HTTPS, HTTP, or SSH protocols)
- Clone operations have a 300-second timeout
- `--depth 1` shallow clones limit data transfer
- Git commands use `subprocess` with argument arrays (no shell injection)
- No untrusted strings are interpolated into shell commands

### Symlink Protection

- During file discovery, symlinks are resolved and checked
- Files that resolve outside the repository boundary are skipped
- Symlinks in ZIP archives are rejected

### No Code Execution

Repository analysis is purely static:
- No `npm install`, `pip install`, or dependency installation
- No `setup.py`, `Makefile`, or script execution
- No `postinstall` hooks
- Tree-sitter parsing is read-only AST analysis

### File Path Validation

- All file content requests validate that the requested path stays within the repository directory
- Path normalization prevents directory traversal via the API
- Only files within the repository `source/` directory are accessible

### Upload Limits

| Limit | Default | Environment Variable |
|-------|---------|---------------------|
| Max upload size | 500 MB | `MAX_UPLOAD_MB` |
| Max extracted size | 2000 MB | `MAX_EXTRACTED_MB` |
| Max file count | 10000 | `MAX_REPOSITORY_FILES` |
| Max single file | 10 MB | `MAX_FILE_MB` |

### SSRF Protection

- Git clone URLs are validated against common patterns
- Local/private IP addresses should be blocked in production configurations

## Privacy Considerations

### Local Mode

CodeMentor-RAG supports fully local operation:
- **Local embeddings**: sentence-transformers runs locally
- **Local LLM**: Ollama runs locally
- **Local storage**: SQLite + FAISS + BM25 on disk
- **No external API calls** in local mode

### Cloud Provider Privacy

When using cloud LLM providers (OpenAI, etc.):
- Repository source code chunks are sent to the provider's API
- The provider's data handling policies apply
- Consider using local Ollama for sensitive repositories

### Secret Detection

- The system does not intentionally scan for or expose secrets
- However, code chunks sent to LLM providers may contain secrets present in the repository
- Users should ensure sensitive repositories are analyzed with local providers only

## Error Handling

Custom error classes prevent leaking internal paths or sensitive information:
- `ArchiveSecurityError`: Security violations in uploads
- `RepositoryValidationError`: Invalid repository input
- `ParserError`: Parsing failures (logged, not exposed)

Production mode suppresses detailed error messages in HTTP responses.

## Recommendations

1. Use local providers (Ollama + sentence-transformers) for sensitive codebases
2. Do not expose the API publicly without authentication
3. Review upload size limits for your deployment
4. Monitor logs for security-related warnings
5. Keep dependencies updated for security patches
