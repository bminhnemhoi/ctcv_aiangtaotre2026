import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { DocItem, ProcedureCard } from '../src/api/types';
import { previewText } from '../src/components/ExpandableText';
import { vi } from '../src/i18n/vi';
import {
  DocumentsCard,
  caseOptionLabels,
  describeDoc,
  displayCaseLabel,
  isConditional,
} from '../src/screens/DocumentsCard';

// Test-only data, visibly marked "thử" so it can never pass for a real document list.
const LONG_NAME =
  'Giấy tờ, tài liệu thử chứng minh chỗ ở hợp pháp của người đăng ký thử. Trừ trường hợp ' +
  'thông tin thử đã có trong cơ sở dữ liệu thử thì người đăng ký thử không phải nộp thêm ' +
  'giấy tờ thử nào khác, cán bộ thử tự tra cứu và ghi nhận vào hồ sơ thử của người đăng ký.';
const LONG_CASE =
  'Trường hợp thử người đăng ký vào chỗ ở hợp pháp không thuộc quyền sở hữu của mình, gồm ' +
  'vợ về ở với chồng, chồng về ở với vợ, con về ở với cha mẹ, người cao tuổi về ở với anh ' +
  'chị em ruột thử, hồ sơ gồm';

function doc(doc_key: string, name: string, extra: Partial<DocItem> = {}): DocItem {
  return {
    doc_key,
    name,
    case_label: null,
    originals: 1,
    copies: 0,
    form_code: null,
    ...extra,
  };
}

function card(documents: DocItem[]): ProcedureCard {
  const cases = [...new Set(documents.flatMap((d) => (d.case_label ? [d.case_label] : [])))];
  return {
    procedure_id: 'thu-05',
    ten: 'Thủ tục thử',
    co_quan: 'Cơ quan thử',
    source_url: 'https://example.org/du-lieu-thu/thu-05',
    fetched_at: '2026-09-25T02:00:00Z',
    documents,
    fees: [],
    cases,
  };
}

describe('DocumentsCard — tên giấy tờ dài có nút Xem đủ', () => {
  it('tên dài: hiện câu đầu kèm số bản, nút Xem đủ mở nguyên văn', async () => {
    const short = previewText(LONG_NAME) ?? '';
    render(<DocumentsCard procedure={card([doc('d01', LONG_NAME), doc('d02', 'Tờ khai thử')])} />);
    const box = screen.getByTestId('doc-item-d01');
    const row = box.closest('[data-testid="doc-row-d01"]') as HTMLElement;
    expect(row).not.toBeNull();
    expect(row).toHaveTextContent(`${short} (bản chính: 1, bản sao: 0)`);
    expect(row).not.toHaveTextContent('cán bộ thử tự tra cứu');

    const more = screen.getByTestId('more-doc-item-d01');
    expect(more).toHaveTextContent(vi.docs.showMore);
    const user = userEvent.setup();
    await user.click(more);
    expect(row).toHaveTextContent(describeDoc(doc('d01', LONG_NAME)));
    expect(more).toHaveTextContent(vi.docs.showLess);
    // The button only opens the text: it never ticks the box.
    expect(box).not.toBeChecked();
    await user.click(screen.getByText(describeDoc(doc('d01', LONG_NAME))));
    expect(box).toBeChecked();
  });

  it('tên ngắn thì không có nút Xem đủ', () => {
    render(<DocumentsCard procedure={card([doc('d02', 'Tờ khai thử')])} />);
    expect(screen.getByTestId('doc-item-d02')).toBeInTheDocument();
    expect(screen.queryByTestId('more-doc-item-d02')).toBeNull();
    expect(screen.queryByRole('button', { name: vi.docs.showMore })).toBeNull();
  });

  it('nhãn trường hợp dài cũng được rút gọn, có nút Xem đủ riêng', async () => {
    render(
      <DocumentsCard
        procedure={card([
          doc('d01', 'Tờ khai thử'),
          doc('d03', 'Hợp đồng thử', { case_label: LONG_CASE }),
        ])}
      />,
    );
    const shown = displayCaseLabel(LONG_CASE);
    const legend = screen.getByText(previewText(shown) ?? '');
    expect(legend.closest('legend')).not.toBeNull();
    const group = legend.closest('fieldset') as HTMLElement;
    const user = userEvent.setup();
    await user.click(within(group).getByRole('button', { name: vi.docs.showMore }));
    expect(within(group).getByText(shown)).toBeVisible();
  });
});

describe('giấy tờ chỉ cần khi đúng trường hợp', () => {
  it('isConditional nhận cờ conditional hoặc trạng thái neu_ap_dung', () => {
    expect(isConditional(doc('d01', 'Tờ khai thử'))).toBe(false);
    expect(isConditional(doc('d01', 'Tờ khai thử', { conditional: false }))).toBe(false);
    expect(isConditional(doc('d01', 'Tờ khai thử', { conditional: null }))).toBe(false);
    expect(isConditional(doc('d01', 'Tờ khai thử', { conditional: true }))).toBe(true);
    expect(isConditional({ ...doc('d01', 'Tờ khai thử'), status: 'neu_ap_dung' })).toBe(true);
    expect(isConditional({ ...doc('d01', 'Tờ khai thử'), status: 'thieu' })).toBe(false);
  });

  it('thẻ giấy tờ ghi rõ "chỉ cần nếu đúng trường hợp" ngay trong nhãn ô đánh dấu', () => {
    const conditional = doc('d02', 'Trường hợp thử định cư ở nước ngoài thì nộp tờ khai thử', {
      conditional: true,
    });
    render(<DocumentsCard procedure={card([doc('d01', 'Tờ khai thử'), conditional])} />);
    const box = screen.getByTestId('doc-item-d02');
    expect(box).toHaveAccessibleName(new RegExp(`^${vi.docs.conditional}`));
    expect(screen.getByTestId('doc-item-d01')).not.toHaveAccessibleName(
      new RegExp(vi.docs.conditional),
    );
  });
});

describe('caseOptionLabels — chữ trong ô chọn trường hợp', () => {
  it('nhãn dài được rút gọn; nhãn ngắn giữ như displayCaseLabel', () => {
    const out = caseOptionLabels(['Hồ sơ thử gồm', LONG_CASE]);
    expect(out[0]).toBe('Hồ sơ thử');
    expect(out[1]).toBe(previewText(displayCaseLabel(LONG_CASE)));
  });

  it('hai nhãn dài trùng phần đầu thì giữ nguyên văn để không chọn nhầm', () => {
    const head = LONG_CASE.slice(0, 150);
    const a = `${head} thứ nhất thử`;
    const b = `${head} thứ hai thử`;
    const out = caseOptionLabels([a, b]);
    expect(out).toEqual([displayCaseLabel(a), displayCaseLabel(b)]);
    expect(new Set(out).size).toBe(2);
  });
});
